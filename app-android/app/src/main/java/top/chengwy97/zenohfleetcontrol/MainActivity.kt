@file:OptIn(androidx.compose.foundation.layout.ExperimentalLayoutApi::class, androidx.compose.material3.ExperimentalMaterial3Api::class)
package top.chengwy97.zenohfleetcontrol

import android.content.Context
import android.os.Bundle
import android.os.Handler
import android.os.Looper
import android.webkit.MimeTypeMap
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.activity.compose.rememberLauncherForActivityResult
import androidx.activity.result.contract.ActivityResultContracts
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.ExperimentalLayoutApi
import androidx.compose.foundation.layout.FlowRow
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.ArrowDropDown
import androidx.compose.material.icons.filled.AttachFile
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material.icons.filled.Devices
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.AssistChip
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.DropdownMenu
import androidx.compose.material3.DropdownMenuItem
import androidx.compose.material3.ElevatedAssistChip
import androidx.compose.material3.FilledTonalButton
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.Scaffold
import androidx.compose.material3.SegmentedButton
import androidx.compose.material3.SegmentedButtonDefaults
import androidx.compose.material3.SingleChoiceSegmentedButtonRow
import androidx.compose.material3.Surface
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.remember
import androidx.compose.runtime.saveable.rememberSaveable
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import android.database.Cursor
import android.net.Uri
import org.json.JSONObject
import java.io.ByteArrayOutputStream
import java.net.HttpURLConnection
import java.net.URL
import java.net.URLEncoder
import java.security.SecureRandom
import java.security.cert.X509Certificate
import java.util.UUID
import java.util.concurrent.Executors
import kotlin.concurrent.Volatile
import kotlinx.coroutines.delay
import javax.net.ssl.HostnameVerifier
import javax.net.ssl.HttpsURLConnection
import javax.net.ssl.SSLContext
import javax.net.ssl.X509TrustManager

class MainActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            MaterialTheme {
                FleetControlApp()
            }
        }
    }
}

private enum class ConsoleTab(val label: String) {
    Devices("Devices"),
    Session("Session"),
    Attachments("Attachments"),
    Output("Output")
}

private enum class SessionState(val label: String) {
    Idle("idle"),
    Running("running"),
    WaitingApproval("waiting_approval"),
    Queued("queued"),
    Ended("ended")
}

private enum class DeviceStatus(val label: String) {
    Online("online"),
    Busy("busy"),
    Offline("offline")
}

private data class DeviceRow(
    val name: String,
    val status: DeviceStatus,
    val sessionId: String,
    val cwd: String,
)

private data class SessionEvent(
    val kind: String,
    val detail: String,
)

private data class DirectoryEntry(
    val name: String,
    val path: String,
    val kind: String,
)

private data class ConsoleMessage(
    val title: String,
    val detail: String,
)

private data class ApprovalRequest(
    val approvalId: String,
    val cmdId: String,
    val reason: String,
    val risk: String,
    val action: String,
)

private data class AttachmentItem(
    val uri: Uri,
    val name: String,
    val mimeType: String,
)

private data class AttachmentUpload(
    val item: AttachmentItem,
    val status: String,
    val detail: String,
    val transferUri: String? = null,
)

private data class DeviceSummary(
    val device: DeviceRow,
    val sessionState: SessionState,
    val eventCount: Int,
    val resultCount: Int,
)

private data class ConsoleState(
    val device: DeviceRow,
    val sessionId: String,
    val sessionState: SessionState,
    val cwd: String,
    val commandText: String,
    val directoryPath: String,
    val directories: List<DirectoryEntry>,
    val events: List<SessionEvent>,
    val messages: List<ConsoleMessage>,
    val results: List<ConsoleMessage>,
    val approvals: List<ApprovalRequest> = emptyList(),
)

private data class UploadResponse(
    val transferId: String,
    val uploadUrl: String,
    val downloadUrl: String,
    val transferUri: String,
)

private data class BridgeAuthToken(
    val accessToken: String,
    val tokenType: String,
    val expiresAt: Int,
)

private data class BridgeDevice(
    val username: String,
    val deviceId: String,
    val status: String? = null,
    val sessionId: String? = null,
    val cwd: String? = null,
)

private data class BridgeSession(
    val username: String,
    val deviceId: String,
    val sessionId: String,
    val state: String? = null,
    val cwd: String? = null,
    val lastCommand: String? = null,
    val events: List<SessionEvent> = emptyList(),
    val results: List<ConsoleMessage> = emptyList(),
    val approvals: List<ApprovalRequest> = emptyList(),
)

private val backgroundExecutor = Executors.newSingleThreadExecutor()
@Volatile private var lastAttachmentUploadError: String? = null

private const val DEFAULT_BRIDGE_BASE_URL = "https://10.0.2.2:8443"
private const val FILE_API_BASE_URL = "http://10.0.2.2:8080"
private const val FILE_API_TOKEN = "dev-token-change-me"
private const val PREFS_NAME = "zfc_bridge"
private const val PREF_BRIDGE_BASE_URL = "bridge_base_url"
private const val PREF_BRIDGE_USERNAME = "bridge_username"
private const val PREF_BRIDGE_PASSWORD = "bridge_password"
private const val PREF_BRIDGE_TOKEN = "bridge_token"
private const val PREF_BRIDGE_EXPIRES_AT = "bridge_expires_at"

private fun urlEncode(value: String): String =
    URLEncoder.encode(value, Charsets.UTF_8.name()).replace("+", "%20")

private fun sessionPath(username: String, deviceId: String, sessionId: String): String =
    "/v1/sessions/${urlEncode(username)}/${urlEncode(deviceId)}/${urlEncode(sessionId)}"

private fun directoryEntriesFor(device: DeviceRow, path: String): List<DirectoryEntry> = when (device.name) {
    "dev_pdf_downloads" -> when (path) {
        "/home/eame/Downloads" -> listOf(
            DirectoryEntry("Projects", "/home/eame/Downloads/Projects", "dir"),
            DirectoryEntry("Screenshots", "/home/eame/Downloads/Screenshots", "dir"),
            DirectoryEntry("prompt.txt", "/home/eame/Downloads/prompt.txt", "file"),
        )
        "/home/eame/Downloads/Projects" -> listOf(
            DirectoryEntry("notes.md", "/home/eame/Downloads/Projects/notes.md", "file"),
            DirectoryEntry("report.pdf", "/home/eame/Downloads/Projects/report.pdf", "file"),
        )
        else -> listOf(
            DirectoryEntry("Downloads", "/home/eame/Downloads", "dir"),
        )
    }
    "dev_android_sim" -> when (path) {
        "/home/eame/Downloads" -> listOf(
            DirectoryEntry("android-app", "/home/eame/Downloads/android-app", "dir"),
            DirectoryEntry("apk", "/home/eame/Downloads/apk", "dir"),
        )
        else -> listOf(
            DirectoryEntry("Downloads", "/home/eame/Downloads", "dir"),
        )
    }
    else -> when (path) {
        "/home/eame/cwy/zenoh/zenoh-fleet-control" -> listOf(
            DirectoryEntry("README.md", "/home/eame/cwy/zenoh/zenoh-fleet-control/README.md", "file"),
            DirectoryEntry("app-android", "/home/eame/cwy/zenoh/zenoh-fleet-control/app-android", "dir"),
            DirectoryEntry("agent-python", "/home/eame/cwy/zenoh/zenoh-fleet-control/agent-python", "dir"),
        )
        else -> listOf(
            DirectoryEntry("zenoh-fleet-control", "/home/eame/cwy/zenoh/zenoh-fleet-control", "dir"),
        )
    }
}

private fun parentDirectory(path: String): String = when {
    path == "/" -> "/"
    path.lastIndexOf('/') <= 0 -> "/"
    else -> path.substringBeforeLast('/')
}

private fun nextDirectoryState(state: ConsoleState, path: String): ConsoleState {
    val normalized = if (path.endsWith('/')) path.dropLast(1) else path
    val entries = directoryEntriesFor(state.device, normalized)
    return state.copy(
        cwd = normalized,
        directoryPath = normalized,
        directories = entries,
        events = state.events + SessionEvent("cwd", normalized),
        messages = state.messages + ConsoleMessage("cwd", "switched to $normalized"),
    )
}

private fun nextSessionState(state: ConsoleState, sessionState: SessionState, detail: String): ConsoleState = state.copy(
    sessionState = sessionState,
    events = state.events + SessionEvent("state", detail),
    messages = state.messages + ConsoleMessage("state", detail),
)

private fun cancelTask(state: ConsoleState): ConsoleState = state.copy(
    sessionState = SessionState.Idle,
    events = state.events + SessionEvent("cancelled", state.commandText.ifBlank { "(empty command)" }),
    messages = state.messages + ConsoleMessage("cancel", "active task cancelled"),
    results = state.results + ConsoleMessage("cancel", "task cancelled by user"),
)

private fun endSession(state: ConsoleState): ConsoleState = state.copy(
    sessionState = SessionState.Ended,
    events = state.events + SessionEvent("ended", "session ended by user"),
    messages = state.messages + ConsoleMessage("session", "session closed"),
    results = state.results + ConsoleMessage("session", "history preserved for review"),
)

private fun restartSession(state: ConsoleState): ConsoleState = state.copy(
    sessionId = "sess_${UUID.randomUUID().toString().replace("-", "").take(8)}",
    sessionState = SessionState.Idle,
    commandText = "",
    events = listOf(SessionEvent("created", "new session started")),
    messages = listOf(ConsoleMessage("session", "new session ready")),
    results = listOf(ConsoleMessage("result", "clean session created")),
)

private fun sendCommand(state: ConsoleState): ConsoleState {
    val prompt = state.commandText.ifBlank { "(empty command)" }
    return state.copy(
        sessionState = SessionState.Running,
        events = state.events + listOf(
            SessionEvent("accepted", prompt),
            SessionEvent("progress", "command started"),
        ),
        messages = state.messages + ConsoleMessage("command", prompt),
        results = state.results + listOf(
            ConsoleMessage("result", "running in ${state.cwd}"),
            ConsoleMessage("result", "completed locally in the simulator"),
        ),
    )
}

private fun queueCommand(state: ConsoleState): ConsoleState = state.copy(
    sessionState = SessionState.Queued,
    events = state.events + SessionEvent("queued", state.commandText.ifBlank { "(empty command)" }),
    messages = state.messages + ConsoleMessage("queue", "queued for later execution"),
    results = state.results + ConsoleMessage("queue", state.commandText.ifBlank { "(empty command)" }),
)

private fun requestApproval(state: ConsoleState): ConsoleState {
    val cmdId = "cmd_${UUID.randomUUID().toString().replace("-", "").take(8)}"
    val approvalId = "approval_${UUID.randomUUID().toString().replace("-", "").take(8)}"
    return state.copy(
        sessionState = SessionState.WaitingApproval,
        approvals = state.approvals + ApprovalRequest(
            approvalId = approvalId,
            cmdId = cmdId,
            reason = "manual approval required in simulator",
            risk = "high",
            action = state.commandText.ifBlank { "run_ai" },
        ),
        events = state.events + SessionEvent("approval_request", approvalId),
        messages = state.messages + ConsoleMessage("approval", "waiting for user approval"),
    )
}

private fun resolveApproval(state: ConsoleState, approvalId: String, decision: String): ConsoleState = state.copy(
    approvals = state.approvals.filterNot { it.approvalId == approvalId },
    events = state.events + SessionEvent("approval_result", "$approvalId:$decision"),
    messages = state.messages + ConsoleMessage("approval", "$approvalId -> $decision"),
)

private fun resolveDisplayName(context: android.content.Context, uri: Uri): String {
    val cursor: Cursor? = context.contentResolver.query(uri, null, null, null, null)
    cursor?.use {
        val nameIndex = it.getColumnIndex(android.provider.OpenableColumns.DISPLAY_NAME)
        if (nameIndex >= 0 && it.moveToFirst()) {
            val name = it.getString(nameIndex)
            if (!name.isNullOrBlank()) return name
        }
    }
    return uri.lastPathSegment?.substringAfterLast('/') ?: uri.toString()
}

private fun resolveMimeType(context: android.content.Context, uri: Uri): String {
    val mime = context.contentResolver.getType(uri)
    if (!mime.isNullOrBlank()) return mime
    val extension = resolveDisplayName(context, uri).substringAfterLast('.', missingDelimiterValue = "")
    if (extension.isBlank()) return "application/octet-stream"
    return MimeTypeMap.getSingleton().getMimeTypeFromExtension(extension.lowercase()) ?: "application/octet-stream"
}

private fun computeSha256(data: ByteArray): String {
    val digest = java.security.MessageDigest.getInstance("SHA-256")
    return digest.digest(data).joinToString("") { "%02x".format(it) }
}

private fun openBytes(context: android.content.Context, uri: Uri): ByteArray {
    context.contentResolver.openInputStream(uri).use { input ->
        if (input == null) return ByteArray(0)
        val buffer = ByteArrayOutputStream()
        val bytes = ByteArray(8 * 1024)
        while (true) {
            val read = input.read(bytes)
            if (read <= 0) break
            buffer.write(bytes, 0, read)
        }
        return buffer.toByteArray()
    }
}

private fun bridgeRequest(
    baseUrl: String,
    method: String,
    path: String,
    token: String? = null,
    body: String? = null,
): String {
    val url = URL("${baseUrl.trimEnd('/')}$path")
    val connection = (url.openConnection() as HttpURLConnection).apply {
        requestMethod = method
        connectTimeout = 15_000
        readTimeout = 30_000
        setRequestProperty("Content-Type", "application/json")
        if (!token.isNullOrBlank()) {
            setRequestProperty("Authorization", "Bearer $token")
        }
        doInput = true
    }
    if (BuildConfig.DEBUG && url.host == "10.0.2.2" && connection is HttpsURLConnection) {
        connection.sslSocketFactory = debugLocalhostSslContext().socketFactory
        connection.hostnameVerifier = HostnameVerifier { _, _ -> true }
    }
    if (body != null) {
        connection.doOutput = true
        connection.outputStream.use { it.write(body.toByteArray(Charsets.UTF_8)) }
    }
    val status = connection.responseCode
    val stream = if (status in 200..299) connection.inputStream else connection.errorStream
    val responseText = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
    if (status !in 200..299) {
        throw IllegalStateException("bridge request failed: HTTP $status $responseText")
    }
    return responseText
}

private fun debugLocalhostSslContext(): SSLContext {
    val trustAll = object : X509TrustManager {
        override fun checkClientTrusted(chain: Array<out X509Certificate>?, authType: String?) = Unit
        override fun checkServerTrusted(chain: Array<out X509Certificate>?, authType: String?) = Unit
        override fun getAcceptedIssuers(): Array<X509Certificate> = emptyArray()
    }
    return SSLContext.getInstance("TLS").apply {
        init(null, arrayOf(trustAll), SecureRandom())
    }
}

private fun bridgeLogin(baseUrl: String, username: String, password: String): BridgeAuthToken {
    val response = bridgeRequest(
        baseUrl = baseUrl,
        method = "POST",
        path = "/v1/auth/login",
        body = JSONObject().apply {
            put("username", username)
            put("password", password)
        }.toString(),
    )
    val json = JSONObject(response)
    return BridgeAuthToken(
        accessToken = json.getString("access_token"),
        tokenType = json.getString("token_type"),
        expiresAt = json.getInt("expires_at"),
    )
}

private fun bridgeListDevices(baseUrl: String, token: String): List<BridgeDevice> {
    val response = bridgeRequest(baseUrl, "GET", "/v1/devices", token = token)
    val json = JSONObject(response)
    val items = json.optJSONArray("items") ?: return emptyList()
    return List(items.length()) { index ->
        val item = items.getJSONObject(index)
        BridgeDevice(
            username = item.optString("username"),
            deviceId = item.optString("device_id"),
            status = if (item.isNull("status")) null else item.getString("status"),
            sessionId = when {
                !item.isNull("session_id") -> item.getString("session_id")
                !item.isNull("active_session_id") -> item.getString("active_session_id")
                else -> null
            },
            cwd = if (item.isNull("cwd")) null else item.getString("cwd"),
        )
    }
}

private fun bridgeReadSession(baseUrl: String, token: String, username: String, deviceId: String, sessionId: String): BridgeSession {
    val response = bridgeRequest(baseUrl, "GET", sessionPath(username, deviceId, sessionId), token = token)
    val json = JSONObject(response)
    val state = json.opt("state") ?: json.opt("status")
    val events = parseSessionEvents(json)
    return BridgeSession(
        username = json.optString("username", username),
        deviceId = json.optString("device_id", deviceId),
        sessionId = json.optString("session_id", sessionId),
        state = if (state is String) state else state?.toString(),
        cwd = if (json.isNull("cwd")) null else json.getString("cwd"),
        lastCommand = json.optJSONObject("last_command")?.optJSONObject("payload")?.let {
            if (it.isNull("prompt")) null else it.getString("prompt")
        },
        events = events,
        results = parseSessionResults(json),
        approvals = parseApprovalRequests(json),
    )
}

private fun bridgeReadDirectory(baseUrl: String, token: String, username: String, deviceId: String, sessionId: String, path: String): List<DirectoryEntry> {
    val response = bridgeRequest(
        baseUrl,
        "GET",
        "${sessionPath(username, deviceId, sessionId)}/directory?path=${urlEncode(path)}",
        token = token,
    )
    val json = JSONObject(response)
    val entries = json.optJSONArray("entries") ?: return emptyList()
    return List(entries.length()) { index ->
        val entry = entries.getJSONObject(index)
        val absolutePath = entry.optString("path", entry.optString("relative_path", entry.optString("name")))
        val kind = entry.optString("kind", "file")
        DirectoryEntry(
            name = entry.optString("name", absolutePath.substringAfterLast('/')),
            path = absolutePath,
            kind = if (kind == "directory") "dir" else kind,
        )
    }
}

private fun parseSessionEvents(json: JSONObject): List<SessionEvent> {
    val items = json.optJSONArray("events") ?: return emptyList()
    return List(items.length()) { index ->
        val event = items.optJSONObject(index)
        if (event == null) {
            SessionEvent("event", items.optString(index))
        } else {
            val content = event.opt("content")
            val detail = when (content) {
                is JSONObject -> content.optString("text", content.toString())
                null -> event.optString("detail", event.toString())
                else -> content.toString()
            }
            SessionEvent(event.optString("kind", "event"), detail)
        }
    }
}

private fun parseSessionResults(json: JSONObject): List<ConsoleMessage> {
    val results = json.optJSONObject("results") ?: return emptyList()
    return results.keys().asSequence().map { key ->
        val value = results.opt(key)
        val detail = when (value) {
            is JSONObject -> value.optJSONObject("content")?.optString("text", value.toString()) ?: value.optString("text", value.toString())
            null -> ""
            else -> value.toString()
        }
        ConsoleMessage(key, detail)
    }.toList()
}

private fun parseApprovalRequests(json: JSONObject): List<ApprovalRequest> {
    val items = json.optJSONArray("events") ?: return emptyList()
    val approvals = mutableListOf<ApprovalRequest>()
    for (index in 0 until items.length()) {
        val event = items.optJSONObject(index) ?: continue
        if (event.optString("kind") != "approval_request") continue
        val content = event.optJSONObject("content") ?: JSONObject()
        approvals.add(
            ApprovalRequest(
                approvalId = content.optString("approval_id", event.optString("approval_id", "approval_unknown")),
                cmdId = event.optString("cmd_id", content.optString("cmd_id", "cmd_unknown")),
                reason = content.optString("reason", content.optString("text", event.toString())),
                risk = content.optString("risk", "unknown"),
                action = content.optString("action", "approval required"),
            )
        )
    }
    return approvals
}

private fun bridgeSendCommand(baseUrl: String, token: String, username: String, session: ConsoleState, type: String, payload: JSONObject): JSONObject {
    val response = bridgeRequest(
        baseUrl = baseUrl,
        method = "POST",
        path = "${sessionPath(username, session.device.name, session.sessionId)}/commands",
        token = token,
        body = JSONObject().apply {
            put("username", username)
            put("device_id", session.device.name)
            put("session_id", session.sessionId)
            put("type", type)
            put("payload", payload)
        }.toString(),
    )
    return JSONObject(response)
}

private fun bridgeSendControl(baseUrl: String, token: String, username: String, session: ConsoleState, type: String, payload: JSONObject = JSONObject()): JSONObject {
    val response = bridgeRequest(
        baseUrl = baseUrl,
        method = "POST",
        path = "${sessionPath(username, session.device.name, session.sessionId)}/control",
        token = token,
        body = JSONObject().apply {
            put("username", username)
            put("device_id", session.device.name)
            put("session_id", session.sessionId)
            put("type", type)
            put("payload", payload)
        }.toString(),
    )
    return JSONObject(response)
}

private fun requestUploadRef(
    username: String,
    deviceId: String,
    sessionId: String,
    name: String,
    archive: String,
    size: Int,
    sha256: String,
): UploadResponse {
    val body = JSONObject().apply {
        put("username", username)
        put("device_id", deviceId)
        put("session_id", sessionId)
        put("name", name)
        put("archive", archive)
        put("size", size)
        put("sha256", sha256)
    }.toString().toByteArray(Charsets.UTF_8)
    val connection = (URL("$FILE_API_BASE_URL/v1/transfers/uploads").openConnection() as HttpURLConnection).apply {
        requestMethod = "POST"
        setRequestProperty("Authorization", "Bearer $FILE_API_TOKEN")
        setRequestProperty("Content-Type", "application/json")
        doOutput = true
        connectTimeout = 15_000
        readTimeout = 30_000
    }
    connection.outputStream.use { it.write(body) }
    val status = connection.responseCode
    val stream = if (status in 200..299) connection.inputStream else connection.errorStream
    val responseText = stream?.bufferedReader()?.use { it.readText() }.orEmpty()
    if (status !in 200..299) {
        throw IllegalStateException("file-api upload request failed: HTTP $status $responseText")
    }
    val json = JSONObject(responseText)
    return UploadResponse(
        transferId = json.getString("transfer_id"),
        uploadUrl = json.getString("upload_url"),
        downloadUrl = json.getString("download_url"),
        transferUri = json.getString("uri"),
    )
}

private fun uploadBytes(uploadUrl: String, mimeType: String, data: ByteArray) {
    val connection = (URL(uploadUrl).openConnection() as HttpURLConnection).apply {
        requestMethod = "PUT"
        setRequestProperty("Content-Type", mimeType)
        doOutput = true
        connectTimeout = 15_000
        readTimeout = 30_000
    }
    connection.outputStream.use { it.write(data) }
    val status = connection.responseCode
    val errorText = connection.errorStream?.bufferedReader()?.use { it.readText() }.orEmpty()
    if (status !in 200..299) {
        throw IllegalStateException("upload failed: HTTP $status $errorText")
    }
}

private fun uploadAttachment(
    context: android.content.Context,
    username: String,
    deviceId: String,
    sessionId: String,
    item: AttachmentItem,
): AttachmentUpload {
    val data = openBytes(context, item.uri)
    if (data.isEmpty()) {
        return AttachmentUpload(item, "failed", "empty attachment")
    }
    val sha256 = computeSha256(data)
    val response = requestUploadRef(
        username = username,
        deviceId = deviceId,
        sessionId = sessionId,
        name = item.name,
        archive = "raw",
        size = data.size,
        sha256 = sha256,
    )
    uploadBytes(response.uploadUrl, item.mimeType, data)
    return AttachmentUpload(
        item = item,
        status = "uploaded",
        detail = "size=${data.size} sha256=$sha256",
        transferUri = response.transferUri,
    )
}

private fun summarizeDevices(devices: List<DeviceRow>, states: List<ConsoleState>): List<DeviceSummary> = devices.mapIndexed { index, device ->
    val state = states[index]
    val status = when (state.sessionState) {
        SessionState.Running, SessionState.WaitingApproval, SessionState.Queued -> DeviceStatus.Busy
        SessionState.Ended -> DeviceStatus.Offline
        SessionState.Idle -> device.status
    }
    DeviceSummary(
        device = device.copy(status = status),
        sessionState = state.sessionState,
        eventCount = state.events.size,
        resultCount = state.results.size,
    )
}

@Composable
fun FleetControlApp() {
    val context = LocalContext.current
    val prefs = remember { context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE) }
    val mainHandler = remember { Handler(Looper.getMainLooper()) }
    val savedToken = remember {
        val token = prefs.getString(PREF_BRIDGE_TOKEN, null)
        val expiresAt = prefs.getInt(PREF_BRIDGE_EXPIRES_AT, 0)
        if (!token.isNullOrBlank() && expiresAt > (System.currentTimeMillis() / 1000).toInt()) token else null
    }
    val bridgeTokenState = rememberSaveable { mutableStateOf(savedToken) }
    var bridgeBaseUrl by rememberSaveable { mutableStateOf(prefs.getString(PREF_BRIDGE_BASE_URL, DEFAULT_BRIDGE_BASE_URL) ?: DEFAULT_BRIDGE_BASE_URL) }
    val bridgePassword = rememberSaveable { mutableStateOf(prefs.getString(PREF_BRIDGE_PASSWORD, "") ?: "") }
    val bridgeUsername = rememberSaveable { mutableStateOf(prefs.getString(PREF_BRIDGE_USERNAME, "eame") ?: "eame") }
    val devices = remember { mutableStateListOf<DeviceRow>() }
    var activeTab by rememberSaveable { mutableStateOf(ConsoleTab.Devices) }
    var selectedDeviceIndex by rememberSaveable { mutableStateOf(0) }
    var attachmentMenu by rememberSaveable { mutableStateOf(false) }
    val attachments = remember { mutableStateListOf<AttachmentItem>() }
    val uploads = remember { mutableStateListOf<AttachmentUpload>() }
    val states = remember { mutableStateListOf<ConsoleState>() }
    var bridgeStatus by rememberSaveable { mutableStateOf("disconnected") }
    var connectionEditing by rememberSaveable { mutableStateOf(false) }

    fun syncFromBridge() {
        val token = bridgeTokenState.value ?: return
        val username = bridgeUsername.value
        val draftBySession = states.associate { it.sessionId to it.commandText }
        backgroundExecutor.execute {
            try {
                val deviceItems = bridgeListDevices(bridgeBaseUrl, token)
                val mappedDevices = deviceItems.map { item ->
                    DeviceRow(
                        name = item.deviceId,
                        status = when (item.status?.lowercase()) {
                            "busy" -> DeviceStatus.Busy
                            "offline" -> DeviceStatus.Offline
                            else -> DeviceStatus.Online
                        },
                        sessionId = item.sessionId ?: "sess_${item.deviceId}",
                        cwd = item.cwd ?: "/home/eame",
                    )
                }
                val mappedStates = mappedDevices.map { device ->
                    val session = bridgeReadSession(bridgeBaseUrl, token, username, device.name, device.sessionId)
                    val sessionState = when (session.state?.lowercase()) {
                        "running" -> SessionState.Running
                        "waiting_approval" -> SessionState.WaitingApproval
                        "queued" -> SessionState.Queued
                        "ended" -> SessionState.Ended
                        else -> SessionState.Idle
                    }
                    ConsoleState(
                        device = device,
                        sessionId = session.sessionId,
                        sessionState = sessionState,
                        cwd = session.cwd ?: device.cwd,
                        commandText = draftBySession[session.sessionId]?.takeIf { it.isNotEmpty() }
                            ?: session.lastCommand ?: "",
                        directoryPath = session.cwd ?: device.cwd,
                        directories = try {
                            bridgeReadDirectory(bridgeBaseUrl, token, username, device.name, session.sessionId, session.cwd ?: device.cwd)
                        } catch (_: Exception) {
                            directoryEntriesFor(device, session.cwd ?: device.cwd)
                        },
                        events = session.events,
                        messages = listOf(ConsoleMessage("session", "connected to ${device.name}")),
                        results = session.results,
                        approvals = session.approvals,
                    )
                }
                mainHandler.post {
                    devices.clear()
                    devices.addAll(mappedDevices.ifEmpty {
                        listOf(DeviceRow("dev_local", DeviceStatus.Offline, "sess_local", "/home/eame/cwy/zenoh/zenoh-fleet-control"))
                    })
                    states.clear()
                    states.addAll(mappedStates.ifEmpty {
                        devices.map { device ->
                            ConsoleState(
                                device = device,
                                sessionId = device.sessionId,
                                sessionState = SessionState.Idle,
                                cwd = device.cwd,
                                commandText = "",
                                directoryPath = device.cwd,
                                directories = directoryEntriesFor(device, device.cwd),
                                events = emptyList(),
                                messages = listOf(ConsoleMessage("session", "connected to ${device.name}")),
                                results = emptyList(),
                                approvals = emptyList(),
                            )
                        }
                    })
                    bridgeStatus = "connected"
                }
            } catch (_: Exception) {
                mainHandler.post {
                    if (devices.isEmpty()) {
                        devices.addAll(
                            listOf(
                                DeviceRow("dev_pdf_downloads", DeviceStatus.Online, "sess_pdf_downloads", "/home/eame/Downloads"),
                                DeviceRow("dev_android_sim", DeviceStatus.Busy, "sess_android_sim", "/home/eame/Downloads"),
                                DeviceRow("dev_local", DeviceStatus.Offline, "sess_local", "/home/eame/cwy/zenoh/zenoh-fleet-control"),
                            )
                        )
                    }
                    if (states.isEmpty()) {
                        devices.forEachIndexed { index, device ->
                            states.add(
                                ConsoleState(
                                    device = device,
                                    sessionId = device.sessionId,
                                    sessionState = if (index == 0) SessionState.Running else if (index == 1) SessionState.Queued else SessionState.Ended,
                                    cwd = device.cwd,
                                    commandText = if (index == 2) "重新开始一个完整会话" else "",
                                    directoryPath = device.cwd,
                                    directories = directoryEntriesFor(device, device.cwd),
                                    events = emptyList(),
                                    messages = listOf(ConsoleMessage("session", "simulated state")),
                                    results = emptyList(),
                                    approvals = emptyList(),
                                )
                            )
                        }
                    }
                    bridgeStatus = "simulation"
                }
            }
        }
    }

    fun loginAndSync() {
        val username = bridgeUsername.value
        val password = bridgePassword.value
        backgroundExecutor.execute {
            try {
                val token = bridgeLogin(bridgeBaseUrl, username, password)
                mainHandler.post {
                    bridgeTokenState.value = token.accessToken
                    bridgeStatus = "auth ok"
                    connectionEditing = false
                    prefs.edit()
                        .putString(PREF_BRIDGE_BASE_URL, bridgeBaseUrl)
                        .putString(PREF_BRIDGE_USERNAME, username)
                        .putString(PREF_BRIDGE_PASSWORD, password)
                        .putString(PREF_BRIDGE_TOKEN, token.accessToken)
                        .putInt(PREF_BRIDGE_EXPIRES_AT, token.expiresAt)
                        .apply()
                    syncFromBridge()
                }
            } catch (_: Exception) {
                mainHandler.post {
                    bridgeStatus = "auth failed"
                    if (devices.isEmpty()) {
                        devices.add(DeviceRow("dev_local", DeviceStatus.Offline, "sess_local", "/home/eame/cwy/zenoh/zenoh-fleet-control"))
                    }
                }
            }
        }
    }

    fun submitCommand(kind: String, payload: JSONObject = JSONObject()) {
        val token = bridgeTokenState.value ?: return
        val username = bridgeUsername.value
        val currentState = states.getOrNull(selectedDeviceIndex) ?: return
        backgroundExecutor.execute {
            try {
                when (kind) {
                    "cancel", "end_session", "approval_response" -> bridgeSendControl(bridgeBaseUrl, token, username, currentState, kind, payload)
                    else -> bridgeSendCommand(bridgeBaseUrl, token, username, currentState, kind, payload)
                }
                mainHandler.post { syncFromBridge() }
            } catch (_: Exception) {
                mainHandler.post {
                    bridgeStatus = "bridge send failed"
                }
            }
        }
    }

    LaunchedEffect(Unit) {
        if (bridgeTokenState.value != null) {
            bridgeStatus = "restoring"
            syncFromBridge()
        } else if (bridgePassword.value.isNotBlank() && prefs.contains(PREF_BRIDGE_PASSWORD)) {
            bridgeStatus = "restoring"
            loginAndSync()
        }
    }

    LaunchedEffect(bridgeTokenState.value) {
        if (bridgeTokenState.value != null) {
            while (true) {
                delay(2_000)
                syncFromBridge()
            }
        }
    }

    if (devices.isEmpty()) {
        devices.add(DeviceRow("dev_local", DeviceStatus.Offline, "sess_local", "/home/eame/cwy/zenoh/zenoh-fleet-control"))
    }
    if (states.isEmpty()) {
        devices.forEach { device ->
            states.add(
                ConsoleState(
                    device = device,
                    sessionId = device.sessionId,
                    sessionState = SessionState.Idle,
                    cwd = device.cwd,
                    commandText = "",
                    directoryPath = device.cwd,
                    directories = directoryEntriesFor(device, device.cwd),
                    events = emptyList(),
                    messages = listOf(ConsoleMessage("session", "waiting for bridge login")),
                    results = emptyList(),
                    approvals = emptyList(),
                )
            )
        }
    }

    val attachmentPicker = rememberLauncherForActivityResult(
        contract = ActivityResultContracts.OpenMultipleDocuments(),
    ) { uris ->
        if (uris.isNotEmpty()) {
            uris.forEach { uri ->
                attachments.add(
                    AttachmentItem(
                        uri = uri,
                        name = resolveDisplayName(context, uri),
                        mimeType = resolveMimeType(context, uri),
                    )
                )
            }
            activeTab = ConsoleTab.Attachments
            val selectedDevice = devices[selectedDeviceIndex]
            val selectedSessionId = states[selectedDeviceIndex].sessionId
            uris.map { uri ->
                AttachmentItem(
                    uri = uri,
                    name = resolveDisplayName(context, uri),
                    mimeType = resolveMimeType(context, uri),
                )
            }.forEach { item ->
                uploads.add(AttachmentUpload(item, "uploading", "sending to file-api"))
                backgroundExecutor.execute {
                    val result = try {
                        uploadAttachment(
                            context = context,
                            username = "eame",
                            deviceId = selectedDevice.name,
                            sessionId = selectedSessionId,
                            item = item,
                        )
                    } catch (e: Exception) {
                        AttachmentUpload(item, "failed", e.message ?: "upload failed")
                    }
                    uploads.removeAll { it.item.uri == item.uri }
                    uploads.add(result)
                }
            }
        }
    }

    fun pickAttachments(mimeTypes: Array<String>) {
        val request = if (mimeTypes.isEmpty()) arrayOf("*/*") else mimeTypes
        attachmentPicker.launch(request)
    }

    val state = states[selectedDeviceIndex]
    val deviceSummaries = summarizeDevices(devices, states)

    Scaffold(
        topBar = {
            TopAppBar(
                title = { Text("Zenoh Fleet Control", fontWeight = FontWeight.SemiBold) },
                actions = {
                    IconButton(onClick = { attachmentMenu = true }) {
                        Icon(Icons.Default.AttachFile, contentDescription = "Add attachment")
                    }
                    if (bridgeTokenState.value != null) {
                        IconButton(onClick = { connectionEditing = !connectionEditing }) {
                            Icon(Icons.Default.Settings, contentDescription = "Connection settings")
                        }
                    }
                    DropdownMenu(expanded = attachmentMenu, onDismissRequest = { attachmentMenu = false }) {
                        DropdownMenuItem(
                            text = { Text("Add PDF") },
                            onClick = {
                                attachmentMenu = false
                                pickAttachments(arrayOf("application/pdf"))
                            },
                        )
                        DropdownMenuItem(
                            text = { Text("Add image") },
                            onClick = {
                                attachmentMenu = false
                                pickAttachments(arrayOf("image/*"))
                            },
                        )
                        DropdownMenuItem(
                            text = { Text("Add video") },
                            onClick = {
                                attachmentMenu = false
                                pickAttachments(arrayOf("video/*"))
                            },
                        )
                        DropdownMenuItem(
                            text = { Text("Add audio") },
                            onClick = {
                                attachmentMenu = false
                                pickAttachments(arrayOf("audio/*"))
                            },
                        )
                        DropdownMenuItem(
                            text = { Text("Add file") },
                            onClick = {
                                attachmentMenu = false
                                pickAttachments(arrayOf("*/*"))
                            },
                        )
                    }
                }
            )
        }
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .verticalScroll(rememberScrollState())
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            if (bridgeTokenState.value == null || connectionEditing) Card {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Bridge", fontWeight = FontWeight.SemiBold)
                    Text("status: $bridgeStatus")
                    OutlinedTextField(
                        value = bridgeBaseUrl,
                        onValueChange = {
                            bridgeBaseUrl = it
                            bridgeTokenState.value = null
                            bridgeStatus = "disconnected"
                            connectionEditing = false
                            prefs.edit().remove(PREF_BRIDGE_TOKEN).remove(PREF_BRIDGE_EXPIRES_AT).apply()
                        },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("HTTPS bridge URL") },
                        singleLine = true,
                    )
                    OutlinedTextField(
                        value = bridgeUsername.value,
                        onValueChange = {
                            bridgeUsername.value = it
                            bridgeTokenState.value = null
                            prefs.edit().remove(PREF_BRIDGE_TOKEN).remove(PREF_BRIDGE_EXPIRES_AT).apply()
                        },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("Username") },
                        singleLine = true,
                    )
                    OutlinedTextField(
                        value = bridgePassword.value,
                        onValueChange = {
                            bridgePassword.value = it
                            bridgeTokenState.value = null
                            prefs.edit().remove(PREF_BRIDGE_TOKEN).remove(PREF_BRIDGE_EXPIRES_AT).apply()
                        },
                        modifier = Modifier.fillMaxWidth(),
                        label = { Text("Password") },
                        singleLine = true,
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Button(onClick = { loginAndSync() }) { Text("Connect") }
                        if (bridgeTokenState.value != null) {
                            FilledTonalButton(onClick = { connectionEditing = false }) { Text("Back") }
                        }
                    }
                }
            }

            if (bridgeTokenState.value != null && !connectionEditing) SingleChoiceSegmentedButtonRow(modifier = Modifier.fillMaxWidth()) {
                ConsoleTab.entries.forEachIndexed { index, tab ->
                    SegmentedButton(
                        selected = activeTab == tab,
                        onClick = { activeTab = tab },
                        shape = SegmentedButtonDefaults.itemShape(index, ConsoleTab.entries.size),
                    ) {
                        Text(tab.label)
                    }
                }
            }

            if (bridgeTokenState.value != null && !connectionEditing) when (activeTab) {
                ConsoleTab.Devices -> DevicePane(
                    devices = deviceSummaries,
                    selectedIndex = selectedDeviceIndex,
                    onSelect = { selectedDeviceIndex = it },
                )
                ConsoleTab.Session -> SessionPane(
                    state = state,
                    attachments = attachments,
                    uploads = uploads,
                    onCommandChange = { newText -> states[selectedDeviceIndex] = state.copy(commandText = newText) },
                    onChangeCwd = { newCwd ->
                        submitCommand("set_cwd", JSONObject().apply { put("path", newCwd) })
                        states[selectedDeviceIndex] = nextDirectoryState(state, newCwd)
                    },
                    onSetState = { sessionState, detail ->
                        states[selectedDeviceIndex] = nextSessionState(state, sessionState, detail)
                    },
                    onEnd = {
                        submitCommand("end_session")
                        states[selectedDeviceIndex] = restartSession(endSession(state))
                    },
                    onRun = {
                        submitCommand(
                            "run_ai",
                            JSONObject().apply {
                                put("tool", "codex")
                                put("prompt", state.commandText.ifBlank { "(empty command)" })
                                put("mode", "exec")
                                put("options", JSONObject().apply {
                                    put("sandbox", "workspace-write")
                                    put("approval", "never")
                                })
                            },
                        )
                        states[selectedDeviceIndex] = sendCommand(state)
                    },
                    onQueue = {
                        submitCommand(
                            "run_ai",
                            JSONObject().apply {
                                put("tool", "codex")
                                put("prompt", state.commandText.ifBlank { "(empty command)" })
                                put("mode", "exec")
                                put("options", JSONObject().apply {
                                    put("sandbox", "workspace-write")
                                    put("approval", "never")
                                })
                            },
                        )
                        states[selectedDeviceIndex] = queueCommand(state)
                    },
                    onCancel = {
                        submitCommand("cancel")
                        states[selectedDeviceIndex] = cancelTask(state)
                    },
                    onRequestApproval = {
                        states[selectedDeviceIndex] = requestApproval(state)
                    },
                    onResolveApproval = { approvalId, decision ->
                        submitCommand(
                            "approval_response",
                            JSONObject().apply {
                                put("approval_id", approvalId)
                                put("decision", decision)
                                state.approvals.firstOrNull { it.approvalId == approvalId }?.cmdId?.let { put("cmd_id", it) }
                            },
                        )
                        states[selectedDeviceIndex] = resolveApproval(state, approvalId, decision)
                    },
                    onPickAttachment = { mimeTypes -> pickAttachments(mimeTypes) },
                )
                ConsoleTab.Attachments -> AttachmentPane(
                    attachments = attachments,
                    uploads = uploads,
                    onPickAttachment = { mimeTypes -> pickAttachments(mimeTypes) },
                )
                ConsoleTab.Output -> OutputPane(state)
            }
        }
    }
}

@Composable
private fun DevicePane(devices: List<DeviceSummary>, selectedIndex: Int, onSelect: (Int) -> Unit) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Devices", style = MaterialTheme.typography.titleLarge)
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            DeviceStatus.entries.forEach { status ->
                val count = devices.count { it.device.status == status }
                AssistChip(onClick = {}, label = { Text("${status.label}: $count") })
            }
        }
        devices.forEachIndexed { index, device ->
            Card(
                colors = CardDefaults.cardColors(
                    containerColor = if (index == selectedIndex) MaterialTheme.colorScheme.primaryContainer else MaterialTheme.colorScheme.surface,
                ),
                onClick = { onSelect(index) },
            ) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        Text(device.device.name, fontWeight = FontWeight.SemiBold)
                        AssistChip(onClick = {}, label = { Text(device.device.status.label) })
                    }
                    Text("session: ${device.device.sessionId}")
                    Text("cwd: ${device.device.cwd}")
                    Text("session state: ${device.sessionState.label}")
                    Text("events: ${device.eventCount}  results: ${device.resultCount}")
                }
            }
        }
    }
}

@Composable
private fun SessionPane(
    state: ConsoleState,
    attachments: List<AttachmentItem>,
    uploads: List<AttachmentUpload>,
    onCommandChange: (String) -> Unit,
    onChangeCwd: (String) -> Unit,
    onSetState: (SessionState, String) -> Unit,
    onCancel: () -> Unit,
    onRequestApproval: () -> Unit,
    onResolveApproval: (String, String) -> Unit,
    onEnd: () -> Unit,
    onRun: () -> Unit,
    onQueue: () -> Unit,
    onPickAttachment: (Array<String>) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Session", style = MaterialTheme.typography.titleLarge)
        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("active device: ${state.device.name}", fontWeight = FontWeight.SemiBold)
                Text("session: ${state.sessionId}")
                Text("cwd: ${state.cwd}")
                Text("state: ${state.sessionState.label}")
            }
        }
        OutlinedTextField(
            value = state.commandText,
            onValueChange = onCommandChange,
            modifier = Modifier.fillMaxWidth(),
            label = { Text("Command or prompt") },
            minLines = 3,
        )
        Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            Button(onClick = onRun) { Text("Send") }
            FilledTonalButton(onClick = onQueue) { Text("Queue") }
            FilledTonalButton(onClick = { onPickAttachment(arrayOf("*/*")) }) { Text("Attach file") }
        }
        FlowRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
            ElevatedAssistChip(
                onClick = { onChangeCwd(parentDirectory(state.directoryPath)) },
                label = { Text("Up") },
                leadingIcon = { Icon(Icons.Default.ArrowDropDown, null) },
            )
            ElevatedAssistChip(onClick = onCancel, label = { Text("Cancel task") }, leadingIcon = { Icon(Icons.Default.Cancel, null) })
            ElevatedAssistChip(onClick = onEnd, label = { Text("End session") }, leadingIcon = { Icon(Icons.Default.Stop, null) })
            ElevatedAssistChip(onClick = onRun, label = { Text("Run Codex") }, leadingIcon = { Icon(Icons.Default.PlayArrow, null) })
            FilledTonalButton(onClick = onRequestApproval) { Text("Request approval") }
        }
        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Current directory entries: ${state.directoryPath}", fontWeight = FontWeight.SemiBold)
                state.directories.forEach { entry ->
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.SpaceBetween,
                        verticalAlignment = Alignment.CenterVertically,
                    ) {
                        Column(Modifier.weight(1f)) {
                            Text(entry.name, fontWeight = FontWeight.SemiBold)
                            Text(entry.path)
                        }
                        FilledTonalButton(onClick = { onChangeCwd(entry.path) }) {
                            Text(if (entry.kind == "dir") "Open" else "Use")
                        }
                    }
                }
            }
        }
        if (attachments.isNotEmpty()) {
            Card {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Selected attachments", fontWeight = FontWeight.SemiBold)
                    attachments.forEach { attachment ->
                        Text("${attachment.name}  (${attachment.mimeType})")
                    }
                }
            }
        }
        if (uploads.isNotEmpty()) {
            Card {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Upload status", fontWeight = FontWeight.SemiBold)
                    uploads.forEach { upload ->
                        Column(verticalArrangement = Arrangement.spacedBy(2.dp)) {
                            Text(upload.item.name, fontWeight = FontWeight.SemiBold)
                            Text(upload.status)
                            Text(upload.detail)
                            if (upload.transferUri != null) {
                                Text(upload.transferUri)
                            }
                        }
                    }
                }
            }
        }
        if (state.approvals.isNotEmpty()) {
            Card {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("Approvals", fontWeight = FontWeight.SemiBold)
                    state.approvals.forEach { approval ->
                        Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(approval.action, fontWeight = FontWeight.SemiBold)
                            Text(approval.reason)
                            Text("risk: ${approval.risk}")
                            Text("approval: ${approval.approvalId}")
                            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                                Button(onClick = { onResolveApproval(approval.approvalId, "approve") }) { Text("Approve") }
                                FilledTonalButton(onClick = { onResolveApproval(approval.approvalId, "reject") }) { Text("Reject") }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun AttachmentPane(
    attachments: List<AttachmentItem>,
    uploads: List<AttachmentUpload>,
    onPickAttachment: (Array<String>) -> Unit,
) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Attachments", style = MaterialTheme.typography.titleLarge)
        Card {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Pick a real file, image, PDF, video, or audio from the phone. The app will upload bytes through file-api/MinIO and only send the attachment reference through Zenoh.")
                Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    AssistChip(onClick = { onPickAttachment(arrayOf("application/pdf")) }, label = { Text("PDF") }, leadingIcon = { Icon(Icons.Default.Add, null) })
                    AssistChip(onClick = { onPickAttachment(arrayOf("image/*")) }, label = { Text("Image") }, leadingIcon = { Icon(Icons.Default.Add, null) })
                    AssistChip(onClick = { onPickAttachment(arrayOf("video/*")) }, label = { Text("Video") }, leadingIcon = { Icon(Icons.Default.Add, null) })
                    AssistChip(onClick = { onPickAttachment(arrayOf("audio/*")) }, label = { Text("Audio") }, leadingIcon = { Icon(Icons.Default.Add, null) })
                    AssistChip(onClick = { onPickAttachment(arrayOf("*/*")) }, label = { Text("File") }, leadingIcon = { Icon(Icons.Default.Add, null) })
                }
            }
        }
        if (attachments.isNotEmpty()) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Current selection", fontWeight = FontWeight.SemiBold)
                attachments.forEach { attachment ->
                    Card {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(attachment.name, fontWeight = FontWeight.SemiBold)
                            Text(attachment.mimeType)
                            Text(attachment.uri.toString())
                        }
                    }
                }
            }
        }
        if (uploads.isNotEmpty()) {
            Column(verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("Transferred", fontWeight = FontWeight.SemiBold)
                uploads.filter { it.status == "uploaded" }.forEach { upload ->
                    Card {
                        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                            Text(upload.item.name, fontWeight = FontWeight.SemiBold)
                            Text(upload.detail)
                            if (upload.transferUri != null) {
                                Text(upload.transferUri)
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun OutputPane(state: ConsoleState) {
    Column(verticalArrangement = Arrangement.spacedBy(12.dp)) {
        Text("Output", style = MaterialTheme.typography.titleLarge)
        Text("Results", fontWeight = FontWeight.SemiBold)
        state.messages.forEach { message ->
            Card {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(message.title, fontWeight = FontWeight.SemiBold)
                    Text(message.detail)
                }
            }
        }
        state.results.forEach { result ->
            Card {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(4.dp)) {
                    Text(result.title, fontWeight = FontWeight.SemiBold)
                    Text(result.detail)
                }
            }
        }
        Surface {
            Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                Text("event stream", fontWeight = FontWeight.SemiBold)
                state.events.forEach { event ->
                    Text("${event.kind}: ${event.detail}")
                }
            }
        }
    }
}
