package io.github.levydeng.starsavior

import android.content.Context
import android.graphics.Color
import android.graphics.drawable.GradientDrawable
import android.view.View
import android.widget.Button
import android.widget.LinearLayout
import android.widget.TextView

object Ui {
    val blue = Color.rgb(53, 125, 185)
    val ink = Color.rgb(34, 59, 86)
    val background = Color.rgb(241, 247, 252)
    fun dp(context: Context, value: Int) = (value * context.resources.displayMetrics.density).toInt()
    fun surface(color: Int = Color.WHITE, radius: Float = 18f) = GradientDrawable().apply {
        setColor(color); cornerRadius = radius; setStroke(1, Color.rgb(203, 223, 238))
    }
    fun column(context: Context) = LinearLayout(context).apply {
        orientation = LinearLayout.VERTICAL
        setPadding(dp(context, 16), dp(context, 12), dp(context, 16), dp(context, 12))
        setBackgroundColor(Ui.background)
    }
    fun label(context: Context, value: String, size: Float = 16f) = TextView(context).apply {
        text = value; textSize = size; setTextColor(ink)
        setPadding(0, dp(context, 6), 0, dp(context, 6))
    }
    fun button(context: Context, value: String, primary: Boolean = false, action: () -> Unit) = Button(context).apply {
        text = value; isAllCaps = false
        setTextColor(if (primary) Color.WHITE else ink)
        background = surface(if (primary) blue else Color.WHITE)
        setOnClickListener { action() }
        layoutParams = LinearLayout.LayoutParams(-1, dp(context, 48)).apply {
            topMargin = dp(context, 8)
        }
    }
    fun text(context: Context, key: String): String {
        val lang = preferences(context).getString("language", "zh-CN") ?: "zh-CN"
        val index = GuideConverter.languages.indexOf(lang).coerceAtLeast(0)
        return extras[key]?.get(index) ?: Vocabulary(AppState.repository(context).vocabulary, lang).text(key)
    }
    fun preferences(context: Context) = context.getSharedPreferences("settings", Context.MODE_PRIVATE)
    private val extras = mapOf(
        "recognition_failed" to listOf("识别失败", "辨識失敗", "Recognition failed", "認識に失敗しました", "인식 실패"),
        "copy_diagnostics" to listOf("复制诊断信息", "複製診斷資訊", "Copy diagnostics", "診断情報をコピー", "진단 정보 복사"),
        "diagnostics_copied" to listOf("诊断信息已复制", "診斷資訊已複製", "Diagnostics copied", "診断情報をコピーしました", "진단 정보를 복사했습니다"),
        "floating_size" to listOf("悬浮按钮大小", "懸浮按鈕大小", "Floating button size", "フローティングボタンのサイズ", "플로팅 버튼 크기"),
        "floating_transparency" to listOf("透明度（0% 不透明）", "透明度（0% 不透明）", "Transparency (0% opaque)", "透明度（0% 不透明）", "투명도 (0% 불투명)"),
        "floating_preview" to listOf("实际大小预览", "實際大小預覽", "Actual-size preview", "実寸プレビュー", "실제 크기 미리보기"),
        "screen_permission" to listOf("授权屏幕捕获并启动", "授權螢幕擷取並啟動", "Authorize capture and start", "画面共有を許可して開始", "화면 캡처 허용 및 시작"),
        "overlay_permission" to listOf("允许显示悬浮窗", "允許顯示浮動視窗", "Allow floating windows", "オーバーレイを許可", "플로팅 창 허용"),
        "stop_capture" to listOf("停止悬浮识别", "停止浮動辨識", "Stop floating capture", "画面認識を停止", "플로팅 인식 중지"),
        "capture_active" to listOf("悬浮识别已启动", "浮動辨識已啟動", "Floating capture is active", "画面認識が有効です", "플로팅 인식 실행 중"),
        "capture_hint" to listOf("切换到游戏，全屏横向显示事件后点击星形按钮。长按打开菜单。", "切換到遊戲，全螢幕橫向顯示事件後點擊星形按鈕。長按開啟選單。", "Open the game in fullscreen landscape and tap the star. Long-press for the menu.", "ゲームを横向き全画面で表示し、星を押してください。長押しでメニュー。", "게임을 가로 전체 화면으로 열고 별을 누르세요. 길게 누르면 메뉴가 열립니다."),
        "capture_timeout" to listOf("没有收到新画面，请返回游戏重试。", "沒有收到新畫面，請返回遊戲重試。", "No fresh frame. Return to the game and retry.", "新しいフレームがありません。ゲームで再試行してください。", "새 프레임이 없습니다. 게임으로 돌아가 다시 시도하세요."),
        "capture_denied" to listOf("屏幕捕获未获授权。", "螢幕擷取未獲授權。", "Screen capture was not authorized.", "画面共有が許可されていません。", "화면 캡처가 허용되지 않았습니다."),
        "no_data" to listOf("请先同步网站攻略。", "請先同步網站攻略。", "Sync website guides first.", "先に攻略を同期してください。", "먼저 공략을 동기화하세요."),
        "verify_result" to listOf("已显示最高匹配候选，请核对选项及支援卡。", "已顯示最高匹配候選，請核對選項及支援卡。", "Showing the top candidate. Verify choices and support card.", "最上位候補です。選択肢とアルカナを確認してください。", "최상위 후보입니다. 선택지와 아르카나를 확인하세요."),
        "share_hint" to listOf("请先同步攻略。仅支持游戏全屏横屏模式；点击启动后授权悬浮窗和整个屏幕捕获。识别画面不会上传。", "請先同步攻略。僅支援遊戲全螢幕橫向模式；啟動後授權浮動視窗與全螢幕擷取。畫面不會上傳。", "Sync guides first. Fullscreen landscape games only. Start requests overlay and full-display capture permission. Images remain local.", "先に攻略を同期してください。横向き全画面のみ対応。開始後にオーバーレイと画面全体の共有を許可。画像は送信しません。", "먼저 공략을 동기화하세요. 가로 전체 화면만 지원합니다. 시작 후 오버레이와 전체 화면 캡처를 허용하세요. 이미지는 업로드하지 않습니다."),
        "ssl_settings" to listOf("SSL 设置", "SSL 設定", "SSL settings", "SSL 設定", "SSL 설정"),
        "ssl_warning" to listOf("跳过校验后无法验证服务器身份，下载数据可能被篡改。仅影响攻略同步，建议排障后恢复校验。", "略過驗證後無法確認伺服器身分，資料可能遭竄改。僅影響攻略同步，請於排障後恢復驗證。", "Skipping verification permits server impersonation and data tampering. Guide synchronization only. Restore verification after troubleshooting.", "検証を省略するとサーバーの偽装やデータ改ざんを検出できません。攻略同期のみ対象です。問題解決後に検証を戻してください。", "검증을 건너뛰면 서버 사칭이나 데이터 변조를 확인할 수 없습니다. 공략 동기화에만 적용됩니다. 문제 해결 후 검증을 복원하세요."),
        "landscape_only" to listOf("请将游戏切换到全屏横屏模式后识别。", "請將遊戲切換到全螢幕橫向模式後辨識。", "Use the game in fullscreen landscape before scanning.", "ゲームを横向き全画面にしてから認識してください。", "게임을 가로 전체 화면으로 전환한 후 인식하세요."),
        "elapsed" to listOf("耗时 {seconds} 秒", "耗時 {seconds} 秒", "Elapsed: {seconds} s", "所要時間：{seconds} 秒", "소요 시간: {seconds}초")
    )
}
