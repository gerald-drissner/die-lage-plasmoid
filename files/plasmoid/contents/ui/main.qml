import QtQuick
import QtQuick.Layouts
import QtQuick.Controls as QQC2
import org.kde.plasma.plasmoid
import org.kde.plasma.core as PlasmaCore
import org.kde.plasma.components as PlasmaComponents3
import org.kde.kirigami as Kirigami

PlasmoidItem {
    id: root

    // Default size when freshly dropped on the desktop.  Users can resize the
    // desktop widget freely; these are just the initial dimensions.  Minimum
    // size hints below prevent the layout from being crushed into nothing.
    width: Kirigami.Units.gridUnit * 32
    height: Kirigami.Units.gridUnit * 47
    // Keep popup sizing on fullRepresentation only. Putting the popup width
    // on the PlasmoidItem itself makes Plasma stretch the compact panel icon,
    // which is visually distracting in compact panel layouts.

    Plasmoid.icon: root.effectivePlasmoidIcon()
    Plasmoid.title: root.displayTitle()
    // The real settings live inside the widget popup because they talk to the
    // local helper service. Hide Plasma's generic configure dialog where the
    // shell honors this flag; the custom context action below opens the real UI.
    Plasmoid.hasConfigurationInterface: false

    // Desktop-only background handling.  In a panel/popup we keep Plasma's
    // native background; on the desktop the user may choose transparent or
    // a custom color.  NoBackground removes Plasma's own border/background.
    Plasmoid.backgroundHints: root.useNativeBackground() ? PlasmaCore.Types.DefaultBackground : PlasmaCore.Types.NoBackground
    toolTipMainText: root.ninaWarningCount() > 0 ? root.t("nina") : root.displayTitle()
    toolTipSubText: root.panelTooltipText()

    Plasmoid.contextualActions: [
        PlasmaCore.Action {
            text: root.t("openWidgetSettings")
            icon.name: "configure"
            onTriggered: root.openInternalSettings()
        },
        PlasmaCore.Action {
            text: root.t("refresh")
            icon.name: "view-refresh"
            onTriggered: root.triggerRefresh()
        }
    ]

    // Panel ↔ popup behaviour.  Below switchWidth/Height we show the compact
    // representation; clicking it opens the full representation as a popup.
    // On the desktop, the user resizes the widget past these thresholds and
    // the full representation is shown directly.
    preferredRepresentation: (Plasmoid.formFactor === PlasmaCore.Types.Horizontal
                              || Plasmoid.formFactor === PlasmaCore.Types.Vertical)
                             ? compactRepresentation : fullRepresentation
    switchWidth: Kirigami.Units.gridUnit * 22
    switchHeight: Kirigami.Units.gridUnit * 18

    property int activeServerPort: 8765
    property string localServerPort: "8765"
    readonly property int helperPortMin: 8765
    readonly property int helperPortMax: 8775
    property bool portDiscoveryInProgress: false
    property int pendingServerPort: 0
    property string baseUrl: root.serverUrlForPort(root.activeServerPort)
    readonly property int requestTimeoutMs: 25000
    property var rssData: root.emptyRssData()
    property string errorText: ""

    property bool settingsOpen: false
    property string settingsTab: "general"
    property bool saving: false
    property bool refreshing: false

    property string feedsText: ""
    property string weatherText: ""
    property string ninaText: ""
    property string currenciesText: "USD, GBP, CHF"
    property string marketsText: ""
    property string stocksText: ""
    property string twelveDataApiKey: ""
    property string finnhubApiKey: ""
    property string marketProviderMode: "auto"
    property string prayerCity: "Berlin"
    property string prayerCountry: "Germany"
    property string prayerMethod: "3"
    property string uiFontSize: "18"
    property string uiHighlightColor: ""
    // Desktop-only background: "default", "transparent", or "custom".
    // Panel compact mode and panel popup keep Plasma's normal background.
    property string desktopBackgroundMode: "default"
    property string desktopBackgroundColor: ""
    property string newsFontFamily: ""
    property string newsFontSize: "19"
    property string newsFontSizeOffset: "1"
    // Keep the RSS/news font in step when the global font size changes.
    // The explicit news font setting still works; it simply moves along by
    // the same delta as the main UI font on later changes.
    property int newsSyncBaseFontSize: 18
    property bool newsFontSyncInProgress: false
    property string uiLanguage: "de"
    property string fetchIntervalMinutes: "10"
    property bool bootRefreshEnabled: true
    property string bootRefreshDelaySeconds: "120"

    // Panel-mode appearance: "icon" (small icon + tooltip, default) or
    // "warnings" (compact warning status).  Only relevant when the applet
    // sits in a panel; on the desktop the full representation is shown.
    property string panelMode: "icon"
    // Panel icon selection: "dielage" uses a very small bundled SVG in the
    // compact representation; "theme" uses a named icon from the active
    // Plasma icon theme (Breeze by default). The Widget Explorer metadata
    // uses a package-relative icon where supported by Plasma.
    property string panelIconMode: "dielage"
    property string panelThemeIcon: "view-list-details"
    property bool panelWarningBadge: true
    property string panelNoWarningsMode: "icon"
    // Legacy config key from v1.58.x; kept only so older configs can be read
    // without surprises. The compact panel item now always uses normal icon size.
    property string panelWidth: "24"
    // Width hint for the full popup when the applet sits in a Plasma panel.
    // Desktop widgets are still resized directly on the desktop.
    property string panelPopupWidth: "600"
    property int savedPanelPopupWidth: 600
    property bool panelMiddleClickRefresh: true
    property bool blockHeadingIcons: true
    property bool prayerUpcomingHighlight: true
    readonly property var panelThemeIconPresetNames: [
        "view-list-details",
        "applications-internet",
        "internet-news-reader",
        "view-calendar",
        "weather-clear",
        "view-statistics",
        "network-vpn",
        "emblem-favorite"
    ]

    // Visual options for the desktop/full representation.
    // separatorStyle: "none", "subtle", "strong".
    property string separatorStyle: "subtle"
    property bool newsLinksClickable: true
    // titleStyle: "accent", "plain", "compact".
    property string titleStyle: "accent"

    // ---- v1.51 additions --------------------------------------------------
    // The visible widget version. Kept in sync with metadata.json by the
    // installer / packager. This constant is shown in the About section and
    // sent as part of the User-Agent only by the helper (not by QML).
    readonly property string appVersion: "2.0.4"
    readonly property string projectUrl: "https://github.com/gerald-drissner/die-lage-plasmoid"
    readonly property string latestReleaseUrl: projectUrl + "/releases/latest"
    // The asset name is intentionally stable. Every public release should upload
    // die-lage-latest.zip in addition to the versioned installer ZIP, so first-run
    // users can always click the same download link from the setup screen.
    readonly property string latestInstallerZipUrl: projectUrl + "/releases/latest/download/die-lage-latest.zip"

    // User-chosen custom title; empty string means "use the localized default".
    // Used by Plasmoid.title (which feeds the panel tooltip and popup header)
    // and by the full-representation header label.
    property string customTitle: ""

    // Block order as a list of canonical IDs. Defaults to the historical
    // sequence used before v1.51 so that upgrades look identical until the
    // user reorders. parseBlockOrder() repairs unknown / missing IDs at load
    // time so a hand-edited config can never produce gaps or duplicates.
    property var blockOrder: ["nina", "weather", "prayer", "markets", "news", "system"]
    property var collapsedBlocks: ({})

    // Health flag for the local helper service. Toggled by loadCache() /
    // loadConfig() based on whether the local helper answers. Used to
    // show the helper-missing setup screen instead of an empty popup.
    property bool helperOk: true
    property bool initialLoadDone: false
    property bool configLoaded: false

    property bool showWeather: true
    property bool showPrayer: true
    property bool showNina: true
    property bool showMarkets: true
    property bool showSystem: true
    property bool showSystemInfo: true
    property bool showSystemNetwork: true
    property bool showSystemPublicNetwork: false
    property bool showSystemVpn: true
    property string systemVpnLabel: ""
    property bool showSystemUpdates: true

    property string helperStatusMessage: ""
    property bool helperStatusChecking: false
    property string toolsStatusMessage: ""
    property bool toolsStatusChecking: false
    property bool toolsStatusOk: true
    property bool cacheClearing: false
    property string cacheActionMessage: ""
    property bool cacheActionOk: true
    property bool serviceRestarting: false
    property bool resetConfirmVisible: false
    property bool showMarketCurrencies: true
    property bool showMarketIndices: true
    property bool showMarketStocks: true
    property bool showNews: true

    property int baseFontSize: root.clampInt(root.uiFontSize, 18, 12, 34)
    onBaseFontSizeChanged: root.syncNewsFontToBaseFontChange()
    property int titleSize: root.baseFontSize + 7
    property int sectionSize: root.baseFontSize + 3
    property int bodySize: root.baseFontSize
    // Explicit RSS/news text size. This intentionally uses newsFontSize directly so
    // RSS feed names and headlines can be adjusted independently from the rest of the widget.
    property int newsBodySize: root.clampInt(root.newsFontSize, Math.max(10, root.bodySize + root.clampInt(root.newsFontSizeOffset, 1, -3, 6)), 10, 42)
    property int smallSize: Math.max(10, root.baseFontSize - 3)
    property int prayerSize: Math.max(10, root.baseFontSize - 3)
    property int prayerColumns: root.width >= 620 ? 3 : 2
    property double nowTick: Date.now()
    property color appHighlightColor: root.validHexColor(root.uiHighlightColor) ? root.normalizedHexColor(root.uiHighlightColor) : Kirigami.Theme.highlightColor

    function syncNewsFontToBaseFontChange() {
        if (root.newsFontSyncInProgress) {
            return
        }
        var newBase = root.baseFontSize
        var oldBase = root.newsSyncBaseFontSize > 0 ? root.newsSyncBaseFontSize : newBase
        if (oldBase === newBase) {
            root.newsSyncBaseFontSize = newBase
            return
        }
        var currentNews = root.clampInt(root.newsFontSize, Math.max(10, oldBase + 1), 10, 42)
        var shiftedNews = root.clampInt(currentNews + (newBase - oldBase), Math.max(10, newBase + 1), 10, 42)
        root.newsFontSyncInProgress = true
        root.newsFontSize = String(shiftedNews)
        root.newsFontSizeOffset = String(shiftedNews - newBase)
        root.newsFontSyncInProgress = false
        root.newsSyncBaseFontSize = newBase
    }

    function updateNewsFontSizeFromField(value) {
        root.newsFontSize = value
        var base = root.baseFontSize
        var currentNews = root.clampInt(value, Math.max(10, base + 1), 10, 42)
        root.newsFontSizeOffset = String(currentNews - base)
    }

    function isDesktopApplet() {
        return Plasmoid.formFactor !== PlasmaCore.Types.Horizontal
               && Plasmoid.formFactor !== PlasmaCore.Types.Vertical
    }

    function cleanDesktopBackgroundMode(value) {
        var s = String(value || "default").trim().toLowerCase()
        return (s === "transparent" || s === "custom") ? s : "default"
    }

    function useCustomDesktopBackground() {
        return root.isDesktopApplet()
               && root.cleanDesktopBackgroundMode(root.desktopBackgroundMode) === "custom"
               && root.validHexColor(root.desktopBackgroundColor)
    }

    function useNativeBackground() {
        if (!root.isDesktopApplet()) {
            return true
        }
        var mode = root.cleanDesktopBackgroundMode(root.desktopBackgroundMode)
        if (mode === "transparent") {
            return false
        }
        if (mode === "custom" && root.validHexColor(root.desktopBackgroundColor)) {
            return false
        }
        return true
    }

    function emptyRssData() {
        return {
            "updated": "",
            "feeds": [],
            "errors": [],
            "nina": {"items": []},
            "weather": {"items": []},
            "prayer": {"items": []},
            "markets": {
                "exchange": {"items": []},
                "indices": {"items": []},
                "stocks": {"items": []}
            },
            "system": {"items": []}
        }
    }

    function prepareXhr(xhr, purpose) {
        try {
            xhr.timeout = root.requestTimeoutMs
        } catch (e) {
            // Some old QML runtimes may not expose XMLHttpRequest.timeout.
        }
        xhr.ontimeout = function() {
            root.saving = false
            root.refreshing = false
            root.helperStatusChecking = false
            root.helperOk = false
            root.errorText = root.t("requestTimedOut")
            if (purpose === "status") {
                root.helperStatusMessage = root.t("helperStatusTimeout")
            }
            if (purpose === "cache" || purpose === "config") {
                root.initialLoadDone = true
            }
        }
    }

    function serverUrlForPort(port) {
        return "http://127.0.0.1:" + root.clampInt(port, 8765, root.helperPortMin, root.helperPortMax)
    }

    function helperPortCandidateList(preferredPort) {
        var out = []
        var seen = ({})
        function addCandidate(value) {
            var p = root.clampInt(value, 0, root.helperPortMin, root.helperPortMax)
            if (p >= root.helperPortMin && p <= root.helperPortMax && !seen[p]) {
                out.push(p)
                seen[p] = true
            }
        }
        addCandidate(preferredPort)
        addCandidate(root.pendingServerPort)
        addCandidate(root.clampInt(root.localServerPort, 8765, root.helperPortMin, root.helperPortMax))
        addCandidate(root.activeServerPort)
        for (var p = root.helperPortMin; p <= root.helperPortMax; p++) {
            addCandidate(p)
        }
        return out
    }

    function discoverLocalHelperPort(preferredPort) {
        if (root.portDiscoveryInProgress) {
            return
        }
        root.portDiscoveryInProgress = true
        root.probeLocalHelperPort(root.helperPortCandidateList(preferredPort), 0)
    }

    function probeLocalHelperPort(ports, index) {
        if (index >= ports.length) {
            root.portDiscoveryInProgress = false
            root.helperOk = false
            root.initialLoadDone = true
            root.errorText = root.t("cacheUnavailable") + "0"
            return
        }

        var port = ports[index]
        var xhr = new XMLHttpRequest()
        try {
            xhr.timeout = 300
        } catch (e) {
            // Ignore older QML runtimes without XMLHttpRequest.timeout.
        }
        xhr.ontimeout = function() {
            root.probeLocalHelperPort(ports, index + 1)
        }
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                if (xhr.status === 200) {
                    try {
                        var data = JSON.parse(xhr.responseText || "{}")
                        if (data && data.ok === true
                            && typeof data.version === "string"
                            && /^\d+\.\d+\.\d+$/.test(data.version)
                            && Number(data.local_server_port) === port) {
                            root.activeServerPort = port
                            root.pendingServerPort = 0
                            root.portDiscoveryInProgress = false
                            root.loadConfig(false)
                            return
                        }
                    } catch (e) {
                        // Fall through to next candidate.
                    }
                }
                root.probeLocalHelperPort(ports, index + 1)
            }
        }
        xhr.open("GET", root.serverUrlForPort(port) + "/status?t=" + Date.now())
        xhr.send()
    }

    function isEnglish() {
        return root.uiLanguage === "en"
    }

    function cleanSeparatorStyle(value) {
        var s = String(value || "subtle").trim().toLowerCase()
        return (s === "none" || s === "strong") ? s : "subtle"
    }

    function blockSeparatorVisible(blockId) {
        return root.cleanSeparatorStyle(root.separatorStyle) !== "none"
               && root.hasVisibleBlockBefore(blockId)
    }

    function separatorHeight() {
        return root.cleanSeparatorStyle(root.separatorStyle) === "strong" ? 2 : 1
    }

    function separatorOpacity() {
        return root.cleanSeparatorStyle(root.separatorStyle) === "strong" ? 0.28 : 0.13
    }

    function cleanTitleStyle(value) {
        var s = String(value || "accent").trim().toLowerCase()
        return (s === "plain" || s === "compact") ? s : "accent"
    }

    function titlePixelSize() {
        var style = root.cleanTitleStyle(root.titleStyle)
        if (style === "compact") return Math.max(root.sectionSize, root.titleSize - 4)
        if (style === "plain") return root.titleSize
        return root.titleSize + 2
    }

    function titleColor() {
        return root.cleanTitleStyle(root.titleStyle) === "accent" ? root.appHighlightColor : Kirigami.Theme.textColor
    }

    function titleAccentVisible() {
        return root.cleanTitleStyle(root.titleStyle) === "accent"
    }

    // ---- v1.51 helpers ----------------------------------------------------

    // The title shown at the top of the popup and in tooltips. When the user
    // sets a custom title in settings, it wins; otherwise we fall back to the
    // localized default ("Die Lage" / "Daily Briefing").
    function displayTitle() {
        var custom = String(root.customTitle || "").trim()
        return custom.length > 0 ? custom : root.t("title")
    }

    function cleanPanelIconMode(value) {
        var mode = String(value || "dielage").trim().toLowerCase()
        return mode === "theme" ? "theme" : "dielage"
    }

    function cleanThemeIconName(value) {
        var name = String(value || "view-list-details").trim()
        if (!/^[A-Za-z0-9][A-Za-z0-9._-]{0,80}$/.test(name)) {
            return "view-list-details"
        }
        return name
    }

    function effectivePanelThemeIcon() {
        return root.cleanThemeIconName(root.panelThemeIcon || "view-list-details")
    }

    function cleanPanelNoWarningsMode(value) {
        var mode = String(value || "icon").trim().toLowerCase()
        return (mode === "check" || mode === "dot" || mode === "empty") ? mode : "icon"
    }

    function panelNoWarningText() {
        var mode = root.cleanPanelNoWarningsMode(root.panelNoWarningsMode)
        if (mode === "check") return "✓"
        if (mode === "dot") return "•"
        return ""
    }

    function effectivePlasmoidIcon() {
        // The Widget Explorer can use package-relative icons from contents/.
        // For user-selected theme icons we still return the chosen icon name.
        return root.cleanPanelIconMode(root.panelIconMode) === "theme"
               ? root.effectivePanelThemeIcon()
               : "/icons/dielage.svg"
    }

    function panelCompactWidthPx() {
        // Keep the compact panel item at Plasma's normal icon size.  The
        // configurable width now applies only to the opened panel popup.
        return Kirigami.Units.iconSizes.smallMedium
    }

    function panelPopupWidthPx() {
        return root.clampInt(root.panelPopupWidth, 600, 520, 1400)
    }

    function blockIconName(blockId) {
        var key = String(blockId || "")
        if (key === "weather") return Qt.resolvedUrl("../images/block-weather.svg")
        if (key === "prayer") return Qt.resolvedUrl("../images/block-prayer.svg")

        var icons = {
            "nina": "dialog-warning",
            "system": "computer",
            "markets": "view-statistics",
            "news": "internet-news-reader"
        }
        return icons[key] || "view-list-details"
    }

    function panelThemeIconPresetLabel(name) {
        var labels = {
            "applications-internet": root.t("panelIconPresetInternet"),
            "internet-news-reader": root.t("panelIconPresetNews"),
            "view-calendar": root.t("panelIconPresetCalendar"),
            "weather-clear": root.t("panelIconPresetWeather"),
            "view-list-details": root.t("panelIconPresetList"),
            "view-statistics": root.t("panelIconPresetStats"),
            "network-vpn": root.t("panelIconPresetVpn"),
            "emblem-favorite": root.t("panelIconPresetFavorite")
        }
        return labels[name] || name
    }

    function panelThemeIconPresetLabels() {
        var out = []
        for (var i = 0; i < root.panelThemeIconPresetNames.length; i++) {
            var name = root.panelThemeIconPresetNames[i]
            out.push(root.panelThemeIconPresetLabel(name) + "  (" + name + ")")
        }
        return out
    }

    function panelThemeIconPresetIndex() {
        var current = root.effectivePanelThemeIcon()
        for (var i = 0; i < root.panelThemeIconPresetNames.length; i++) {
            if (root.panelThemeIconPresetNames[i] === current) return i
        }
        return -1
    }

    // Canonical block IDs and their default order. Update both lists together.
    readonly property var allBlockIds: ["weather", "prayer", "nina", "system", "markets", "news"]
    readonly property var defaultBlockOrder: ["nina", "weather", "prayer", "markets", "news", "system"]
    readonly property var blockOrderModel: root.parseBlockOrder(root.blockOrder)

    // Coerce an arbitrary value (string, array, malformed JSON) into a clean
    // list of canonical block IDs, with duplicates removed and any missing
    // IDs appended at the end. This means a hand-edited config can never make
    // a block silently disappear.
    function parseBlockOrder(value) {
        var clean = []
        var seen = {}
        var i

        if (Array.isArray(value)) {
            for (i = 0; i < value.length; i++) {
                var id = String(value[i] || "").trim().toLowerCase()
                if (root.allBlockIds.indexOf(id) >= 0 && !seen[id]) {
                    clean.push(id)
                    seen[id] = true
                }
            }
        }

        for (i = 0; i < root.defaultBlockOrder.length; i++) {
            var fallback = root.defaultBlockOrder[i]
            if (!seen[fallback]) {
                clean.push(fallback)
                seen[fallback] = true
            }
        }

        return clean
    }

    function parseCollapsedBlocks(value) {
        var clean = {}
        if (!value || typeof value !== "object") {
            return clean
        }
        for (var i = 0; i < root.allBlockIds.length; i++) {
            var id = root.allBlockIds[i]
            if (value[id] === true) {
                clean[id] = true
            }
        }
        return clean
    }

    function collapsedBlocksPayload() {
        var payload = {}
        for (var i = 0; i < root.allBlockIds.length; i++) {
            var id = root.allBlockIds[i]
            payload[id] = root.isBlockCollapsed(id)
        }
        return payload
    }

    function isBlockCollapsed(id) {
        return Boolean(root.collapsedBlocks && root.collapsedBlocks[id] === true)
    }

    function toggleBlockCollapsed(id) {
        if (root.allBlockIds.indexOf(id) < 0) {
            return
        }
        var clean = root.parseCollapsedBlocks(root.collapsedBlocks)
        clean[id] = !root.isBlockCollapsed(id)
        root.collapsedBlocks = clean
        root.persistCollapsedBlocks()
    }

    function persistCollapsedBlocks() {
        var xhr = new XMLHttpRequest()
        root.prepareXhr(xhr)

        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4 && xhr.status !== 200) {
                if (xhr.status === 0) {
                    root.helperOk = false
                }
                root.errorText = root.t("saveFailed") + xhr.status
            }
        }

        xhr.open("POST", root.baseUrl + "/config")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.send(JSON.stringify({ "collapsed_blocks": root.collapsedBlocksPayload() }))
    }

    // Move a block one position up or down. Used by the arrow buttons in
    // settings. Out-of-range moves are ignored so the buttons can stay
    // enabled without extra logic.
    function moveBlockUp(id) {
        var order = root.blockOrder.slice()
        var idx = order.indexOf(id)
        if (idx <= 0) return
        var tmp = order[idx - 1]
        order[idx - 1] = order[idx]
        order[idx] = tmp
        root.blockOrder = order
    }

    function moveBlockDown(id) {
        var order = root.blockOrder.slice()
        var idx = order.indexOf(id)
        if (idx < 0 || idx >= order.length - 1) return
        var tmp = order[idx + 1]
        order[idx + 1] = order[idx]
        order[idx] = tmp
        root.blockOrder = order
    }

    function resetBlockOrder() {
        root.blockOrder = root.defaultBlockOrder.slice()
    }

    // Localized human-readable label for a block id, used in the reorder
    // list. Reuses the same translation keys as the section headers, so the
    // labels never drift out of sync with what users see in the news view.
    function blockLabel(id) {
        return root.t(id)
    }

    readonly property var settingsTabIds: ["general", "appearance", "content", "system", "sources", "markets", "prayer", "about"]

    function settingsTabLabel(id) {
        switch (id) {
        case "general": return root.t("settingsTabGeneral")
        case "appearance": return root.t("settingsTabAppearance")
        case "content": return root.t("settingsTabContent")
        case "system": return root.t("settingsTabSystem")
        case "sources": return root.t("settingsTabSources")
        case "markets": return root.t("settingsTabMarkets")
        case "prayer": return root.t("settingsTabPrayer")
        case "about": return root.t("settingsTabAbout")
        }
        return id
    }

    // Whether a block's section is currently visible in the news view.
    // News blocks (weather, prayer, nina, news) follow the user's "show
    // blocks" checkboxes directly. The two derived blocks (system, markets)
    // also honour their content-availability helpers so an empty markets
    // section stays out of the layout.
    function isBlockVisible(id) {
        switch (id) {
        case "weather": return root.showWeather
        case "prayer":  return root.showPrayer
        case "nina":    return root.showNina
        case "system":  return root.hasSystemContent()
        case "markets": return root.hasAnyMarketContent()
        case "news":    return root.showNews
        }
        return false
    }

    // Is there a visible block above `id` in the current order? Used to
    // decide whether to draw the inter-block spacer at the top of `id`.
    function hasVisibleBlockBefore(id) {
        var order = root.blockOrder
        for (var i = 0; i < order.length; i++) {
            if (order[i] === id) return false
            if (root.isBlockVisible(order[i])) return true
        }
        return false
    }

    function t(key) {
        var en = {
            "title": "Daily Briefing",
            "loading": "Loading…",
            "refresh": "Refresh",
            "back": "Back",
            "settings": "Settings",
            "updated": "Updated: ",
            "noCache": "No cache found yet",
            "settingsTitle": "Settings",
            "settingsTabGeneral": "General",
            "settingsTabAppearance": "Appearance",
            "settingsTabContent": "Blocks",
            "settingsTabSystem": "System",
            "settingsTabSources": "Sources",
            "settingsTabMarkets": "Markets",
            "settingsTabPrayer": "Prayer times",
            "settingsTabAbout": "About / service",
            "generalSettings": "General",
            "generalHelp": "Start here: language and widget title. The language setting changes the widget UI, not the language of external RSS headlines.",
            "appearanceSettings": "Appearance and refresh",
            "appearanceHelp": "Controls the widget's visual style, font sizes, refresh interval and panel behavior.",
            "contentSettings": "Visible blocks and order",
            "contentHelp": "Enable or disable blocks and choose their order in the main layout.",
            "dataSourcesSettings": "Sources and services",
            "dataSourcesHelp": "Configure RSS feeds, weather locations, warning areas, markets and prayer-time data. API keys stay local in your config file.",
            "displayUpdate": "Display and updates",
            "separators": "Section separators",
            "separatorNone": "No separators",
            "separatorSubtle": "Subtle separators",
            "separatorStrong": "Stronger separators",
            "separatorHelp": "Controls the divider lines between the main dashboard blocks. Feed dividers inside the news block stay visible for readability.",
            "fontSize": "Font size",
            "fetchInterval": "Fetch interval in minutes",
            "bootRefreshEnabled": "Run first refresh after login/reboot",
            "bootRefreshDelay": "Delay after login/reboot",
            "bootRefreshDelayHelp": "When enabled, Die Lage runs one forced refresh shortly after login/reboot. Default: 120 seconds. Increase this if Wi-Fi, VPN or the network starts slowly. Saving updates the systemd user boot timer for the next login/reboot.",
            "localServerPort": "Local helper port",
            "localServerPortHelp": "Port for the local helper on 127.0.0.1. Allowed range: 8765–8775. Change this only if another local service already uses 8765. Save, then restart the local service; the widget scans this range when reconnecting.",
            "localServerPortActive": "Active port",
            "localServerPortConfigured": "Configured port",
            "portRestartRequired": "The helper port was saved, but the running service is still using the old port. Restart the local service so it can bind to the new port.",
            "activePortShort": "active port:",
            "restartTerminalFallbackShort": "The local helper is unreachable; use the terminal restart command shown below.",
            "restartTerminalFallback": "The local helper is currently unreachable. Run this terminal command, then click Retry: systemctl --user restart dielage-local-server.service",
            "restartLocalService": "Restart local service",
            "restarting": "Restarting…",
            "restartLocalServiceDone": "Local service restart requested. The widget will reconnect automatically.",
            "clearCache": "Clear cache",
            "clearCacheHelp": "Deletes Die Lage cache files in ~/.cache/die-lage. Settings and API keys are kept. After clearing, use Refresh to rebuild fresh data.",
            "clearCacheConfirm": "Clear cached Die Lage data now? Settings and API keys are kept.",
            "clearCacheDone": "Cache cleared. Use Refresh to rebuild fresh data.",
            "clearCacheWorking": "Clearing cache …",
            "clearCacheFailed": "Cache could not be cleared. HTTP ",
            "checkTools": "Check required tools",
            "toolsChecking": "Checking local tools …",
            "toolsRequiredOk": "All good! The required local tools are available.",
            "toolsRequiredFound": "Required tools:",
            "toolsRequiredMissing": "Missing required tools:",
            "toolsRecommendedMissing": "Recommended tools not found:",
            "toolsOptionalFound": "Optional helpers found:",
            "toolsRequiredHint": "Install the missing required tools and run install.sh again. Optional helpers only improve system, VPN or update detection.",
            "toolsCheckFailed": "Tool check failed: HTTP ",
            "highlightColor": "Accent / highlight color",
            "highlightHelp": "Enter a hex color such as #2f7d4f, or leave empty.",
            "highlightPlaceholder": "#2f7d4f or leave empty = Plasma color",
            "plasmaColor": "Plasma color",
            "desktopAppearance": "Desktop background",
            "desktopBackgroundMode": "Background on the desktop",
            "desktopBackgroundDefault": "Plasma default",
            "desktopBackgroundTransparent": "Transparent",
            "desktopBackgroundCustom": "Custom color",
            "desktopBackgroundColor": "Desktop background color",
            "desktopBackgroundPlaceholder": "#101414, empty = Plasma default",
            "desktopBackgroundHelp": "Desktop only. Panels and panel popups keep Plasma's normal background. Transparent removes the widget frame/background; custom color draws a flat background behind the widget content.",
            "newsFont": "News font",
            "newsLinksClickable": "RSS headlines are clickable",
            "newsLinksHelp": "When disabled, headlines are displayed as plain text and clicks do not open links.",
            "newsFontFamily": "Font family for news",
            "newsFontFamilyHint": "Only used if the font is installed. Leave empty for the normal Plasma font.",
            "newsFontSize": "RSS/news font size (px)",
            "newsFontSizeHelp": "Controls only RSS feed names and headlines. Use the general font size above for the rest of the widget.",
            "preview": "Preview: This is a news line with the selected font.",
            "language": "Language / Sprache",
            "blocks": "Show blocks",
            "weather": "Weather",
            "prayer": "Islamic Prayer Times",
            "prayerUpcomingHint": "Coming up soon",
            "prayerNowHint": "Now",
            "nina": "Warnings",
            "markets": "Markets",
            "system": "System",
            "news": "News",
            "rssSources": "RSS sources – one line per source: Name|URL|Count",
            "weatherPlaces": "Weather locations – one line per location: Name|Latitude|Longitude",
            "weatherHelp": "Weather source: Open-Meteo (free for non-commercial use, no API key). Used only to create the compact text/weather display. Coordinates are decimal GPS values; get them from OpenStreetMap, open-meteo.com/en/docs or any geocoder.",
            "ninaAreas": "Warning areas – one line per area/source",
            "ninaHelp": "Supported formats: SOURCE|Name|parameters. NINA|Name|ARS for Germany/BBK, GEOSPHERE|Name|lat|lon for exact Austrian point warnings, METEOALARM|Name|country-slug|include|exclude for European country feeds, NWS|Name|lat|lon|include|exclude for USA/NWS, or URL|Name|feed-url|include|exclude. include/exclude are optional comma-separated filters.",
            "ninaInternationalHelp": "Examples: NINA|Berlin|110000000000 · GEOSPHERE|Bludenz|47.1527|9.8276 · METEOALARM|Austria|austria|Vorarlberg · NWS|El Paso|31.7725|-106.461|El Paso · NWS|Nashville|36.1626|-86.7816|Davidson · URL|Own feed|https://example.org/warnings.atom. For Austria, GEOSPHERE is more precise than the country-wide MeteoAlarm feed.",
            "systemSettings": "System info",
            "showSystemInfo": "Show system details",
            "showSystemNetwork": "Show local network",
            "showSystemPublicNetwork": "Show public IP / ISP",
            "showSystemVpn": "Show VPN status",
            "vpnLabel": "VPN label / manual hint",
            "vpnLabelPlaceholder": "e.g. Mullvad, WARP, WG",
            "vpnLabelHelp": "Optional: if automatic detection cannot name your VPN, enter a short label here. The helper still tries to detect active VPN interfaces first.",
            "showSystemUpdates": "Show available updates",
            "systemHelp": "Compact Linux system data. VPN detection checks local routes, active VPN interfaces and common tools such as NetworkManager, Mullvad, WARP and Tailscale. Public IP/ISP uses an external lookup and is off by default. Everything is cached until the next normal refresh.",
            "marketSettings": "Markets – currencies, indices and stocks",
            "marketSubblocks": "Market sections",
            "showCurrencies": "Show exchange rates",
            "showIndices": "Show indices",
            "showStocks": "Show stocks",
            "emptyMarketHint": "Leave a field empty to hide that section and skip fetching it.",
            "currenciesHelp": "Currencies against EUR, comma-separated. Both directions are shown automatically.",
            "indicesHelp": "Indices – one line per index: Name|Symbol. Yahoo Finance is the safest default; Twelve Data can be forced below.",
            "stocksHelp": "Stocks – one line per stock: Name|Symbol|Display. Optional display can be a WKN, ISIN or short label.",
            "providerMode": "Market data source",
            "providerHint": "Automatic: stocks try API-key providers first; indices try Yahoo first. Choose Twelve Data, Finnhub or Yahoo to prefer one provider; Die Lage still uses fallbacks when a source fails. API keys are optional and stored only locally. Yahoo does not need a key, but is an unofficial fallback.",
            "twelveKey": "Twelve Data API key – optional. Get it from twelvedata.com. Stored locally and used for market data depending on source mode.",
            "finnhubKey": "Finnhub API key – optional. Get it from finnhub.io/register. Stored locally and used as another market-data source.",
            "prayerSettings": "Islamic Prayer Times – location and calculation",
            "prayerHelp": "Source: AlAdhan Prayer Times API. City/country are sent to the API as text; use common English spellings such as Berlin/Germany. If a city is not accepted, use a nearby larger city or check aladhan.com/prayer-times-api.",
            "prayerHighlightUpcoming": "Highlight upcoming prayer time",
            "prayerHighlightUpcomingHelp": "Marks a prayer time shortly before it starts, switches briefly to Now when the time arrives, and clears after about one minute. It is not meant to be a real-time prayer clock.",
            "methodHelp": "Calculation method number: 3 = Muslim World League (common default), 2 = ISNA, 4 = Umm al-Qura Makkah, 5 = Egyptian Authority, 12 = France, 13 = Diyanet Turkey. Full list: aladhan.com/calculation-methods.",
            "city": "City",
            "country": "Country",
            "method": "Method",
            "save": "Save",
            "saving": "Saving…",
            "cancel": "Cancel",
            "location": "Location",
            "ninaOfficial": "Official warning available. Please check details.",
            "noWarningsFor": "No current warnings for ",
            "noWarnings": "No current warnings",
            "warning": "Warning",
            "exchangeRates": "Exchange rates",
            "indices": "Indices",
            "stocks": "Stocks",
            "jsonError": "JSON error: ",
            "cacheUnavailable": "Cache unavailable: HTTP ",
            "configError": "Configuration error: ",
            "configUnavailable": "Configuration unavailable: HTTP ",
            "saveFailed": "Save failed: HTTP ",
            "refreshFailed": "Refresh failed: HTTP ",
            "requestTimedOut": "Request timed out. The local helper did not answer in time.",
            "panelSettings": "Panel appearance",
            "panelMode": "Display when in a panel",
            "panelModeIcon": "Icon with tooltip",
            "panelModeWarnings": "Warning status",
            "openWidgetSettings": "Configure Daily Briefing",
            "panelHelp": "Only used when the widget sits in a Plasma panel. On the desktop the full layout is always shown. Icon mode uses the native Plasma tooltip; warning status shows only current warnings. Click the panel item to open the full view. Right-click also offers Configure Daily Briefing.",
            "panelIconSettings": "Panel icon",
            "panelIconMode": "Icon source",
            "panelIconDielage": "Bundled Die Lage icon",
            "panelIconTheme": "Plasma/Breeze theme icon",
            "panelIconPreset": "Theme icon preset",
            "panelIconName": "Theme icon name",
            "panelIconHelp": "The Widget Explorer icon uses the bundled package icon where Plasma supports it; theme-icon mode uses named Plasma/Breeze icons. To browse available names, install plasma-sdk and open Cuttlefish/Icon Explorer, or search /usr/share/icons.",
            "panelWarningBadge": "Show warning badge on panel icon",
            "panelNoWarningsDisplay": "No-warning display",
            "panelNoWarningsIcon": "Show Die Lage icon",
            "panelNoWarningsCheck": "Green checkmark",
            "panelNoWarningsDot": "Neutral dot",
            "panelNoWarningsEmpty": "Empty / transparent",
            "panelNoWarningsHelp": "The green checkmark simply means: no current warnings are known for the configured warning areas. You can replace it with the icon, a neutral dot, or an empty panel item.",
            "panelPopupWidth": "Panel popup width",
            "panelPopupWidthHelp": "Width of the full popup opened from the panel, in pixels. Empty or invalid input uses the default of 600 px. If the width changes, the panel popup closes once after saving so Plasma can reopen it with the new size.",
            "panelMiddleClickRefresh": "Middle-click refreshes data",
            "panelMiddleClickRefreshHelp": "When enabled, a middle mouse click on the panel item triggers an update instead of opening the popup.",
            "blockHeadingIcons": "Show mini icons before block headings",
            "blockHeadingIconsHelp": "Uses small Plasma/Breeze theme icons before the desktop and popup section titles. The panel icon is configured separately above.",
            "panelIconPresetInternet": "Internet / globe",
            "panelIconPresetNews": "News",
            "panelIconPresetCalendar": "Calendar",
            "panelIconPresetWeather": "Weather",
            "panelIconPresetList": "List",
            "panelIconPresetStats": "Statistics",
            "panelIconPresetVpn": "VPN / network",
            "panelIconPresetFavorite": "Favorite",
            "ninaPlaceholder": "NINA|Berlin|110000000000\nGEOSPHERE|Bludenz|47.1527|9.8276\nMETEOALARM|Austria|austria|Vorarlberg\nNWS|El Paso|31.7725|-106.461|El Paso\nNWS|Nashville|36.1626|-86.7816|Davidson\nURL|Own feed|https://example.org/warnings.atom",
            "customTitle": "Custom title",
            "customTitleHelp": "Replaces the title shown at the top of the popup and in the panel tooltip. Leave empty to use \"Daily Briefing\" / \"Die Lage\".",
            "customTitlePlaceholder": "Leave empty = Daily Briefing",
            "titleStyle": "Title style",
            "titleStyleAccent": "Prominent with accent",
            "titleStylePlain": "Plain",
            "titleStyleCompact": "Compact",
            "titleStyleHelp": "Controls only the main desktop/popup title. The panel keeps its compact icon/status view.",
            "blockOrder": "Order of blocks",
            "blockOrderHelp": "Drag is not used here. Use the arrow buttons to move a block up or down in the layout. Disabled blocks are hidden but keep their position when you re-enable them.",
            "collapseBlock": "Collapse block",
            "expandBlock": "Expand block",
            "collapsedHint": "Collapsed. Click the arrow to show this block again.",
            "moveUp": "Move up",
            "moveDown": "Move down",
            "resetOrder": "Reset to default",
            "resetDefaults": "Reset settings, sources and blocks",
            "resetConfirm": "Reset all settings, sources and block choices to the bundled defaults? RSS feeds, weather locations, warning areas, market lists and display options will be replaced. API keys will be cleared. This cannot be undone.",
            "resetConfirmYes": "Yes, reset",
            "resetConfirmNo": "Cancel",
            "resetDefaultsDone": "Settings were reset to defaults. A refresh has been requested.",
            "secondsUnit": "seconds",
            "aboutSection": "Status & info",
            "aboutStoryTitle": "About Die Lage",
            "aboutStoryText": "Die Lage grew out of a journalist's daily routine: keeping current news, weather, warnings, markets and system context in view without constantly jumping between apps and feeds. I like numbers, statistics and dashboards, but I also need them to stay quiet enough for real work. Islamic prayer times are included because I lived for many years in Islamic countries, where they are a useful part of everyday orientation. I built this first as a working tool for myself; if it helps others too, I am happy to share it. Suggestions for useful additional information blocks are welcome.",
            "aboutVersion": "Version",
            "aboutCopyright": "© 2026 Gerald Drißner · MIT license",
            "contactAuthor": "Contact author",
            "donate": "Donate",
            "checkHelperStatus": "Check service status",
            "helperServiceHelpOk": "The local background services are reachable and should fetch data normally. If updates stop, click the restart button below. Terminal fallback: systemctl --user restart dielage-local-server.service",
            "helperServiceHelpMissing": "The local background service is not reachable. The widget can still show cached data, but refresh, settings sync and new data need this service. Use the repair commands below; if systemd says the unit was not found, run install.sh from the full release zip again.",
            "helperServiceCommands": "Terminal commands:\nsystemctl --user daemon-reload\nsystemctl --user enable --now dielage-local-server.service\nsystemctl --user enable --now dielage-cache.timer dielage-cache-boot.timer\nsystemctl --user restart dielage-local-server.service\nsystemctl --user start dielage-cache.service\nsystemctl --user status dielage-local-server.service --no-pager\nsystemctl --user status dielage-cache.timer --no-pager\njournalctl --user -u dielage-local-server.service -n 80 --no-pager",
            "helperStatusChecking": "Checking service status …",
            "helperStatusOkChecked": "All good! The local background services are running. Version:",
            "helperStatusMissingChecked": "The local background service did not answer. Repair commands are shown below.",
            "helperStatusFailed": "Background-service status check failed: HTTP ",
            "helperStatusTimeout": "The local background service did not answer before the timeout. Repair commands are shown below.",
            "aboutHelperOk": "Local helper service: running",
            "aboutHelperMissing": "Local helper service: not reachable",
            "helperMissingTitle": "Setup needed",
            "helperMissingBody": "This widget needs a small local background service that fetches RSS feeds and other data in the background. If you installed the widget through the KDE Store, only the visible Plasma package is present. The local helper must be installed once from the full installer ZIP.",
            "helperMissingHint": "Click Download installer ZIP, save it to Downloads, unpack it, run the commands below, then click Retry. The ZIP unpacks to die-lage-latest and contains the helper scripts plus systemd user units. No root password is needed because the service runs as a normal systemd user service.",
            "downloadInstallerZip": "Download installer ZIP",
            "uninstallTitle": "Complete removal",
            "uninstallText": "Plasma can remove the visible widget, but not reliably the local helper scripts, cache timer and systemd user units. Use these commands for a clean uninstall.",
            "uninstallCommands": "dielage-uninstall\n# complete removal including config and cache:\ndielage-uninstall --purge\n# if the command is not in PATH:\n~/.local/bin/dielage-uninstall --purge",
            "copyCommand": "Copy command",
            "copied": "Copied",
            "openHomepage": "Project page",
            "retryConnection": "Retry connection"
        }
        var de = {
            "title": "Die Lage",
            "loading": "Lädt…",
            "refresh": "Aktualisieren",
            "back": "Zurück",
            "settings": "Einstellungen",
            "updated": "Aktualisiert: ",
            "noCache": "Noch kein Cache gefunden",
            "settingsTitle": "Einstellungen",
            "settingsTabGeneral": "Allgemein",
            "settingsTabAppearance": "Darstellung",
            "settingsTabContent": "Blöcke",
            "settingsTabSystem": "System",
            "settingsTabSources": "Quellen",
            "settingsTabMarkets": "Märkte",
            "settingsTabPrayer": "Gebetszeiten",
            "settingsTabAbout": "Info / Dienst",
            "generalSettings": "Allgemein",
            "generalHelp": "Beginnen Sie hier: Sprache und Widget-Titel. Die Sprache ändert die Oberfläche des Widgets, nicht die Sprache externer RSS-Meldungen.",
            "appearanceSettings": "Darstellung und Aktualisierung",
            "appearanceHelp": "Steuert Darstellung, Schriftgrößen, Abrufintervall und Panel-Verhalten.",
            "contentSettings": "Sichtbare Blöcke und Reihenfolge",
            "contentHelp": "Aktivieren oder deaktivieren Sie Blöcke und legen Sie deren Reihenfolge im Hauptlayout fest.",
            "dataSourcesSettings": "Quellen und Dienste",
            "dataSourcesHelp": "Konfigurieren Sie RSS-Feeds, Wetterorte, Warngebiete, Märkte und Gebetszeiten. API-Keys bleiben lokal in Ihrer Konfigurationsdatei.",
            "displayUpdate": "Darstellung und Aktualisierung",
            "separators": "Trennlinien zwischen Blöcken",
            "separatorNone": "Keine Trennlinien",
            "separatorSubtle": "Dezente Trennlinien",
            "separatorStrong": "Deutlichere Trennlinien",
            "separatorHelp": "Steuert die Linien zwischen den großen Dashboard-Blöcken. Trennlinien innerhalb der Nachrichten bleiben für die Lesbarkeit erhalten.",
            "fontSize": "Schriftgröße",
            "fetchInterval": "Abruf-Intervall in Minuten",
            "bootRefreshEnabled": "Erste Aktualisierung nach Login/Neustart ausführen",
            "bootRefreshDelay": "Verzögerung nach Login/Neustart",
            "bootRefreshDelayHelp": "Wenn aktiv, führt Die Lage kurz nach Login/Neustart einen erzwungenen Datenabruf aus. Standard: 120 Sekunden. Erhöhen Sie den Wert, wenn WLAN, VPN oder Netzwerk langsam starten. Speichern aktualisiert den systemd-User-Boot-Timer für den nächsten Login/Neustart.",
            "localServerPort": "Lokaler Helper-Port",
            "localServerPortHelp": "Port des lokalen Helpers auf 127.0.0.1. Erlaubter Bereich: 8765–8775. Nur ändern, wenn ein anderer lokaler Dienst bereits 8765 nutzt. Speichern, dann den lokalen Dienst neu starten; das Widget sucht diesen Bereich beim erneuten Verbinden ab.",
            "localServerPortActive": "Aktiver Port",
            "localServerPortConfigured": "Konfigurierter Port",
            "portRestartRequired": "Der Helper-Port wurde gespeichert, aber der laufende Dienst nutzt noch den alten Port. Starten Sie den lokalen Dienst neu, damit er den neuen Port nutzt.",
            "activePortShort": "aktiver Port:",
            "restartTerminalFallbackShort": "Der lokale Helper ist nicht erreichbar; verwenden Sie den unten angezeigten Terminal-Befehl.",
            "restartTerminalFallback": "Der lokale Helper ist derzeit nicht erreichbar. Führen Sie diesen Terminal-Befehl aus und klicken Sie danach auf Erneut verbinden: systemctl --user restart dielage-local-server.service",
            "restartLocalService": "Lokalen Dienst neu starten",
            "restarting": "Neustart läuft …",
            "restartLocalServiceDone": "Neustart des lokalen Dienstes angefordert. Das Widget verbindet sich automatisch neu.",
            "clearCache": "Cache löschen",
            "clearCacheHelp": "Löscht nur Die-Lage-Cache-Dateien in ~/.cache/die-lage. Einstellungen und API-Keys bleiben erhalten. Danach Aktualisieren verwenden, um frische Daten aufzubauen.",
            "clearCacheConfirm": "Zwischengespeicherte Die-Lage-Daten jetzt löschen? Einstellungen und API-Keys bleiben erhalten.",
            "clearCacheDone": "Cache gelöscht. Mit Aktualisieren werden frische Daten aufgebaut.",
            "clearCacheWorking": "Cache wird gelöscht …",
            "clearCacheFailed": "Cache konnte nicht gelöscht werden. HTTP ",
            "checkTools": "Benötigte Werkzeuge prüfen",
            "toolsChecking": "Lokale Werkzeuge werden geprüft …",
            "toolsRequiredOk": "Alles gut! Die notwendigen lokalen Werkzeuge sind vorhanden.",
            "toolsRequiredFound": "Notwendige Werkzeuge:",
            "toolsRequiredMissing": "Es fehlen notwendige Werkzeuge:",
            "toolsRecommendedMissing": "Empfohlene Werkzeuge nicht gefunden:",
            "toolsOptionalFound": "Optionale Helfer gefunden:",
            "toolsRequiredHint": "Installieren Sie fehlende notwendige Werkzeuge und führen Sie install.sh erneut aus. Optionale Helfer verbessern nur System-, VPN- oder Update-Erkennung.",
            "toolsCheckFailed": "Werkzeugprüfung fehlgeschlagen: HTTP ",
            "highlightColor": "Akzentfarbe / Highlight-Farbe",
            "highlightHelp": "Bitte eine Hex-Farbe wie #2f7d4f eintragen, oder leer lassen.",
            "highlightPlaceholder": "#2f7d4f oder leer = Plasma-Farbe",
            "plasmaColor": "Plasma-Farbe",
            "desktopAppearance": "Desktop-Hintergrund",
            "desktopBackgroundMode": "Hintergrund auf dem Desktop",
            "desktopBackgroundDefault": "Plasma-Standard",
            "desktopBackgroundTransparent": "Transparent",
            "desktopBackgroundCustom": "Eigene Farbe",
            "desktopBackgroundColor": "Desktop-Hintergrundfarbe",
            "desktopBackgroundPlaceholder": "#101414, leer = Plasma-Standard",
            "desktopBackgroundHelp": "Nur für die Desktop-Version. Panel und Panel-Popup behalten den normalen Plasma-Hintergrund. Transparent entfernt Rahmen/Hintergrund des Widgets; eigene Farbe zeichnet einen flachen Hintergrund hinter den Inhalt.",
            "newsFont": "Nachrichten-Schrift",
            "newsLinksClickable": "RSS-Überschriften sind anklickbar",
            "newsLinksHelp": "Wenn deaktiviert, werden Überschriften nur als Text angezeigt und Links nicht geöffnet.",
            "newsFontFamily": "Schriftart für Nachrichten",
            "newsFontFamilyHint": "Wird nur genutzt, wenn die Schrift installiert ist. Leer lassen = normale Plasma-Schrift.",
            "newsFontSize": "RSS-/Nachrichten-Schriftgröße (px)",
            "newsFontSizeHelp": "Ändert nur RSS-Quellen und Überschriften. Die allgemeine Schriftgröße oben steuert den Rest des Widgets.",
            "preview": "Vorschau: Dies ist eine Nachrichtenzeile mit der gewählten Schrift.",
            "language": "Sprache / Language",
            "blocks": "Blöcke anzeigen",
            "weather": "Wetter",
            "prayer": "Islamische Gebetszeiten",
            "prayerUpcomingHint": "Steht bald bevor",
            "prayerNowHint": "Jetzt",
            "nina": "Warnmeldungen",
            "markets": "Märkte",
            "system": "System",
            "news": "Nachrichten",
            "rssSources": "RSS-Quellen – eine Zeile pro Quelle: Name|URL|Anzahl",
            "weatherPlaces": "Wetterorte – eine Zeile pro Ort: Name|Breitengrad|Längengrad",
            "weatherHelp": "Wetterquelle: Open-Meteo (für nicht-kommerzielle Nutzung kostenlos, kein API-Key). Wird nur für die kompakte Text-/Wetteranzeige genutzt. Koordinaten sind Dezimal-GPS-Werte; Sie erhalten sie z. B. über OpenStreetMap, open-meteo.com/en/docs oder einen Geocoder.",
            "ninaAreas": "Warnmeldungen – eine Zeile pro Quelle/Gebiet",
            "ninaHelp": "Unterstützte Formate: QUELLE|Name|Parameter. NINA|Name|ARS für Deutschland/BBK, GEOSPHERE|Name|lat|lon für genaue österreichische Punktwarnungen, METEOALARM|Name|country-slug|include|exclude für europäische Länderfeeds, NWS|Name|lat|lon|include|exclude für USA/NWS oder URL|Name|Feed-URL|include|exclude. include/exclude sind optionale komma-getrennte Filter.",
            "ninaInternationalHelp": "Beispiele: NINA|Berlin|110000000000 · GEOSPHERE|Bludenz|47.1527|9.8276 · METEOALARM|Österreich|austria|Vorarlberg · NWS|El Paso|31.7725|-106.461|El Paso · NWS|Nashville|36.1626|-86.7816|Davidson · URL|Eigener Feed|https://example.org/warnings.atom. Für Österreich ist GEOSPHERE genauer als der landesweite MeteoAlarm-Feed.",
            "systemSettings": "Systeminfo",
            "showSystemInfo": "Systemdaten anzeigen",
            "showSystemNetwork": "Lokales Netzwerk anzeigen",
            "showSystemPublicNetwork": "Öffentliche IP / ISP anzeigen",
            "showSystemVpn": "VPN-Status anzeigen",
            "vpnLabel": "VPN-Kürzel / manueller Hinweis",
            "vpnLabelPlaceholder": "z. B. Mullvad, WARP, WG",
            "vpnLabelHelp": "Optional: Wenn die automatische Erkennung Ihr VPN nicht benennen kann, tragen Sie hier ein kurzes Kürzel ein. Der Hintergrunddienst prüft trotzdem zuerst aktive VPN-Interfaces und Routen.",
            "showSystemUpdates": "Verfügbare Updates anzeigen",
            "systemHelp": "Kompakte Linux-Systemdaten. Die VPN-Erkennung prüft lokale Routen, aktive VPN-Interfaces und gängige Werkzeuge wie NetworkManager, Mullvad, WARP und Tailscale. Öffentliche IP/ISP nutzt eine externe Abfrage und ist standardmäßig aus. Alles wird bis zum nächsten normalen Abruf zwischengespeichert.",
            "marketSettings": "Märkte – Währungen, Indizes und Aktien",
            "marketSubblocks": "Marktbereiche",
            "showCurrencies": "Wechselkurse anzeigen",
            "showIndices": "Indizes anzeigen",
            "showStocks": "Aktien anzeigen",
            "emptyMarketHint": "Ein Feld leer lassen, um den Bereich auszublenden und nicht abzurufen.",
            "currenciesHelp": "Währungen gegen EUR – kommagetrennt. Für jede Währung werden automatisch beide Richtungen angezeigt.",
            "indicesHelp": "Indizes – eine Zeile pro Index: Name|Symbol. Yahoo Finance ist der sichere Standard; Twelve Data kann unten erzwungen werden.",
            "stocksHelp": "Aktien – eine Zeile pro Aktie: Name|Symbol|Anzeige. Anzeige kann WKN, ISIN oder Kurzname sein.",
            "providerMode": "Marktdaten-Quelle",
            "providerHint": "Automatisch: Aktien versuchen zuerst Anbieter mit API-Key; Indizes versuchen zuerst Yahoo. Mit Twelve Data, Finnhub oder Yahoo bevorzugen Sie einen Anbieter; Die Lage nutzt bei Fehlern weiterhin Fallbacks. API-Keys sind optional und bleiben lokal gespeichert. Yahoo benötigt keinen Key, ist aber ein inoffizieller Fallback.",
            "twelveKey": "Twelve Data API-Key – optional. Erhältlich über twelvedata.com. Wird lokal gespeichert und je nach Quellenmodus für Marktdaten genutzt.",
            "finnhubKey": "Finnhub API-Key – optional. Erhältlich über finnhub.io/register. Wird lokal gespeichert und als weitere Marktdaten-Quelle genutzt.",
            "prayerSettings": "Islamische Gebetszeiten – Ort und Berechnung",
            "prayerHelp": "Quelle: AlAdhan Prayer Times API. Stadt/Land werden als Text an die API gesendet; verwenden Sie übliche englische Schreibweisen wie Berlin/Germany. Wenn ein Ort nicht akzeptiert wird, nehmen Sie eine größere Stadt in der Nähe oder prüfen Sie aladhan.com/prayer-times-api.",
            "prayerHighlightUpcoming": "Bevorstehende Gebetszeit hervorheben",
            "prayerHighlightUpcomingHelp": "Markiert eine Gebetszeit kurz bevor sie beginnt, wechselt beim Eintritt kurz auf Jetzt und verschwindet nach etwa einer Minute. Das ist bewusst keine Echtzeit-Gebetsuhr.",
            "methodHelp": "Berechnungsmethode als Zahl: 3 = Muslim World League (gängiger Standard), 2 = ISNA, 4 = Umm al-Qura Makkah, 5 = Egyptian Authority, 12 = Frankreich, 13 = Diyanet Türkei. Vollständige Liste: aladhan.com/calculation-methods.",
            "city": "Stadt",
            "country": "Land",
            "method": "Methode",
            "save": "Speichern",
            "saving": "Speichert…",
            "cancel": "Abbrechen",
            "location": "Ort",
            "ninaOfficial": "Amtliche Warnmeldung vorhanden. Bitte Details prüfen.",
            "noWarningsFor": "Keine aktuellen Warnungen für ",
            "noWarnings": "Keine aktuellen Warnungen",
            "warning": "Warnung",
            "exchangeRates": "Wechselkurse",
            "indices": "Indizes",
            "stocks": "Aktien",
            "jsonError": "JSON-Fehler: ",
            "cacheUnavailable": "Cache nicht erreichbar: HTTP ",
            "configError": "Konfigurationsfehler: ",
            "configUnavailable": "Konfiguration nicht erreichbar: HTTP ",
            "saveFailed": "Speichern fehlgeschlagen: HTTP ",
            "refreshFailed": "Aktualisieren fehlgeschlagen: HTTP ",
            "requestTimedOut": "Zeitüberschreitung: Der lokale Hintergrunddienst hat nicht rechtzeitig geantwortet.",
            "panelSettings": "Panel-Darstellung",
            "panelMode": "Darstellung in einem Panel",
            "panelModeIcon": "Symbol mit Tooltip",
            "panelModeWarnings": "Warnstatus",
            "openWidgetSettings": "Die Lage einrichten",
            "panelHelp": "Wird nur verwendet, wenn das Widget in einem Plasma-Panel sitzt. Auf dem Desktop wird immer das vollständige Layout angezeigt. Symbolmodus nutzt den nativen Plasma-Tooltip; Warnstatus zeigt nur aktuelle Warnmeldungen. Ein Klick auf das Panel-Element öffnet die volle Ansicht. Rechtsklick bietet zusätzlich „Die Lage einrichten“.",
            "panelIconSettings": "Panel-Symbol",
            "panelIconMode": "Symbolquelle",
            "panelIconDielage": "Mitgeliefertes Die-Lage-Symbol",
            "panelIconTheme": "Plasma-/Breeze-Themensymbol",
            "panelIconPreset": "Themensymbol-Vorlage",
            "panelIconName": "Themensymbol-Name",
            "panelIconHelp": "Der Symbol-Eintrag für die Miniprogramm-Liste nutzt, wo Plasma es unterstützt, das mitgelieferte Paket-Symbol; der Themensymbol-Modus verwendet benannte Plasma-/Breeze-Symbole. Verfügbare Namen finden Sie mit plasma-sdk und Cuttlefish/Icon Explorer oder unter /usr/share/icons.",
            "panelWarningBadge": "Warn-Badge auf Panel-Symbol anzeigen",
            "panelNoWarningsDisplay": "Anzeige ohne Warnungen",
            "panelNoWarningsIcon": "Die-Lage-Symbol anzeigen",
            "panelNoWarningsCheck": "Grüner Haken",
            "panelNoWarningsDot": "Neutraler Punkt",
            "panelNoWarningsEmpty": "Leer / transparent",
            "panelNoWarningsHelp": "Der grüne Haken bedeutet nur: Für die eingerichteten Warngebiete sind aktuell keine Warnungen bekannt. Sie können stattdessen das Symbol, einen neutralen Punkt oder ein leeres Panel-Element anzeigen lassen.",
            "panelPopupWidth": "Popup-Breite aus dem Panel",
            "panelPopupWidthHelp": "Breite der vollständigen Ansicht, die aus dem Panel heraus geöffnet wird, in Pixeln. Leer oder ungültig verwendet den Standardwert 600 px. Das kleine Panel-Symbol selbst bleibt davon unberührt.",
            "panelMiddleClickRefresh": "Mittelklick aktualisiert Daten",
            "panelMiddleClickRefreshHelp": "Wenn aktiv, löst ein Klick mit der mittleren Maustaste auf das Panel-Element eine Aktualisierung aus, statt das Popup zu öffnen.",
            "blockHeadingIcons": "Mini-Symbole vor Blocküberschriften anzeigen",
            "blockHeadingIconsHelp": "Nutzt kleine Plasma-/Breeze-Themensymbole vor den Überschriften im Desktop und Popup. Das Panel-Symbol wird separat oben eingestellt.",
            "panelIconPresetInternet": "Internet / Globus",
            "panelIconPresetNews": "Nachrichten",
            "panelIconPresetCalendar": "Kalender",
            "panelIconPresetWeather": "Wetter",
            "panelIconPresetList": "Liste",
            "panelIconPresetStats": "Statistik",
            "panelIconPresetVpn": "VPN / Netzwerk",
            "panelIconPresetFavorite": "Favorit",
            "ninaPlaceholder": "NINA|Berlin|110000000000\nGEOSPHERE|Bludenz|47.1527|9.8276\nMETEOALARM|Österreich|austria|Vorarlberg\nNWS|El Paso|31.7725|-106.461|El Paso\nNWS|Nashville|36.1626|-86.7816|Davidson\nURL|Eigener Feed|https://example.org/warnings.atom",
            "customTitle": "Eigener Titel",
            "customTitleHelp": "Ersetzt den Titel oben im Popup und im Panel-Tooltip. Leer lassen = \"Die Lage\" bzw. \"Daily Briefing\".",
            "customTitlePlaceholder": "Leer = Die Lage",
            "titleStyle": "Titel-Darstellung",
            "titleStyleAccent": "Prägnant mit Akzent",
            "titleStylePlain": "Schlicht",
            "titleStyleCompact": "Kompakt",
            "titleStyleHelp": "Gilt nur für die Hauptüberschrift auf Desktop und Popup. Im Panel bleibt die kompakte Symbol-/Statusansicht.",
            "blockOrder": "Reihenfolge der Blöcke",
            "blockOrderHelp": "Drag-and-Drop ist hier nicht aktiv. Mit den Pfeil-Schaltflächen kann jeder Block nach oben oder unten verschoben werden. Ausgeblendete Blöcke werden nicht angezeigt, behalten aber ihre Position für später.",
            "collapseBlock": "Block einklappen",
            "expandBlock": "Block ausklappen",
            "collapsedHint": "Eingeklappt. Mit dem Pfeil wird dieser Block wieder angezeigt.",
            "moveUp": "Nach oben",
            "moveDown": "Nach unten",
            "resetOrder": "Standardreihenfolge wiederherstellen",
            "resetDefaults": "Einstellungen, Quellen und Blöcke zurücksetzen",
            "resetConfirm": "Alle Einstellungen, Quellen und Blockauswahlen wirklich auf die mitgelieferten Standards zurücksetzen? RSS-Feeds, Wetterorte, Warngebiete, Marktlisten und Darstellungsoptionen werden ersetzt. API-Keys werden gelöscht. Dies kann nicht rückgängig gemacht werden.",
            "resetConfirmYes": "Ja, zurücksetzen",
            "resetConfirmNo": "Abbrechen",
            "resetDefaultsDone": "Einstellungen wurden auf Standard zurückgesetzt. Eine Aktualisierung wurde angefordert.",
            "secondsUnit": "Sekunden",
            "aboutSection": "Status & Info",
            "aboutStoryTitle": "Über Die Lage",
            "aboutStoryText": "Die Lage ist aus meinem journalistischen Alltag entstanden: aktuelle Nachrichten, Wetter, Warnmeldungen, Märkte und Systemkontext im Blick behalten, ohne ständig zwischen Apps und Feeds hin und her zu springen. Ich mag Zahlen, Statistiken und Dashboards, aber sie sollen leise genug bleiben, damit man trotzdem arbeiten kann. Die islamischen Gebetszeiten sind enthalten, weil ich viele Jahre in islamisch geprägten Ländern gelebt habe, wo sie im Alltag eine hilfreiche Orientierung geben. Gebaut habe ich das Widget zuerst für mich selbst; wenn es auch anderen hilft, teile ich es gern. Ideen für weitere sinnvolle Infoblöcke sind willkommen.",
            "aboutVersion": "Version",
            "aboutCopyright": "© 2026 Gerald Drißner · MIT-Lizenz",
            "contactAuthor": "Kontakt zum Autor",
            "donate": "Spenden",
            "checkHelperStatus": "Dienststatus prüfen",
            "helperServiceHelpOk": "Die lokalen Hintergrunddienste sind erreichbar und sollten Daten normal abrufen. Falls Aktualisierungen ausbleiben, klicken Sie unten auf Lokalen Dienst neu starten. Terminal-Variante: systemctl --user restart dielage-local-server.service",
            "helperServiceHelpMissing": "Der lokale Hintergrunddienst ist nicht erreichbar. Das Widget kann eventuell noch alte Cache-Daten anzeigen, aber Aktualisierung, Einstellungsabgleich und neue Daten brauchen diesen Dienst. Verwenden Sie die Reparaturbefehle unten; wenn systemd meldet, dass die Unit nicht gefunden wurde, führen Sie install.sh aus dem vollständigen Release-ZIP erneut aus.",
            "helperServiceCommands": "Terminalbefehle:\nsystemctl --user daemon-reload\nsystemctl --user enable --now dielage-local-server.service\nsystemctl --user enable --now dielage-cache.timer dielage-cache-boot.timer\nsystemctl --user restart dielage-local-server.service\nsystemctl --user start dielage-cache.service\nsystemctl --user status dielage-local-server.service --no-pager\nsystemctl --user status dielage-cache.timer --no-pager\njournalctl --user -u dielage-local-server.service -n 80 --no-pager",
            "helperStatusChecking": "Dienststatus wird geprüft …",
            "helperStatusOkChecked": "Alles gut! Die lokalen Hintergrunddienste laufen. Version:",
            "helperStatusMissingChecked": "Der lokale Hintergrunddienst hat nicht geantwortet. Die Reparaturbefehle stehen direkt darunter.",
            "helperStatusFailed": "Prüfung der Hintergrunddienste fehlgeschlagen: HTTP ",
            "helperStatusTimeout": "Der lokale Hintergrunddienst hat vor Ablauf des Timeouts nicht geantwortet. Die Reparaturbefehle stehen direkt darunter.",
            "aboutHelperOk": "Lokaler Hintergrunddienst: läuft",
            "aboutHelperMissing": "Lokaler Hintergrunddienst: nicht erreichbar",
            "helperMissingTitle": "Einrichtung erforderlich",
            "helperMissingBody": "Dieses Widget braucht einen kleinen lokalen Hintergrunddienst, der RSS-Feeds und weitere Daten im Hintergrund abruft. Wenn Sie das Widget über den KDE Store installiert haben, ist nur das sichtbare Plasma-Paket vorhanden. Der lokale Helper muss einmalig aus dem vollständigen Installer-ZIP installiert werden.",
            "helperMissingHint": "Klicken Sie auf Installer-ZIP herunterladen, speichern Sie die Datei im Ordner Downloads, entpacken Sie sie, führen Sie die unten stehenden Befehle aus und klicken Sie danach auf Erneut verbinden. Das ZIP entpackt sich nach die-lage-latest und enthält Helper-Skripte sowie systemd-User-Units. Kein Root-Passwort ist nötig, weil der Dienst als normaler systemd-User-Service läuft.",
            "downloadInstallerZip": "Installer-ZIP herunterladen",
            "uninstallTitle": "Komplett deinstallieren",
            "uninstallText": "Plasma kann das sichtbare Widget entfernen, aber nicht zuverlässig lokale Helper-Skripte, Cache-Timer und systemd-User-Units. Für eine saubere Deinstallation verwenden Sie diese Befehle.",
            "uninstallCommands": "dielage-uninstall\n# vollständig inkl. Konfiguration und Cache:\ndielage-uninstall --purge\n# falls der Befehl nicht im PATH ist:\n~/.local/bin/dielage-uninstall --purge",
            "copyCommand": "Befehl kopieren",
            "copied": "Kopiert",
            "openHomepage": "Projektseite",
            "retryConnection": "Erneut verbinden"
        }
        var dict = root.isEnglish() ? en : de
        return dict[key] || key
    }

    function normalizedHexColor(value) {
        return String(value || "").trim()
    }

    function normalizedFontFamily(value) {
        return String(value || "").trim()
    }

    function isHexDigit(character) {
        if (!character || character.length !== 1) {
            return false
        }

        var code = character.charCodeAt(0)
        return (code >= 48 && code <= 57) || (code >= 65 && code <= 70) || (code >= 97 && code <= 102)
    }

    function validHexColor(value) {
        var s = root.normalizedHexColor(value)

        if (s.length !== 7 || s.charAt(0) !== "#") {
            return false
        }

        for (var i = 1; i < s.length; i++) {
            if (!root.isHexDigit(s.charAt(i))) {
                return false
            }
        }

        return true
    }

    function clampInt(value, fallback, minValue, maxValue) {
        var n = parseInt(String(value).trim())

        if (isNaN(n)) {
            n = fallback
        }

        return Math.max(minValue, Math.min(maxValue, n))
    }

    function twoDigits(value) {
        var n = parseInt(value)

        if (isNaN(n)) {
            n = 0
        }

        return n < 10 ? "0" + n : String(n)
    }

    function htmlEscape(value) {
        return String(value || "")
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#39;")
    }

    function isSafeExternalUrl(value) {
        var url = String(value || "").trim()
        return /^https?:\/\//i.test(url)
    }

    function openExternalUrl(value) {
        var url = String(value || "").trim()
        if (!root.isSafeExternalUrl(url)) {
            return
        }
        Qt.openUrlExternally(url)
    }

    function helperInstallCommands() {
        return "cd ~/Downloads\n"
            + "rm -rf die-lage-latest\n"
            + "unzip -o die-lage-latest.zip\n"
            + "cd die-lage-latest\n"
            + "chmod +x install.sh uninstall.sh emergency-clean-dielage.sh\n"
            + "./install.sh\n"
            + "systemctl --user restart plasma-plasmashell.service"
    }

    function escapeRegExp(value) {
        var raw = String(value || "")
        var specials = "\\^$.*+?()[]{}|"
        var out = ""

        for (var i = 0; i < raw.length; ++i) {
            var ch = raw.charAt(i)
            out += specials.indexOf(ch) >= 0 ? "\\" + ch : ch
        }

        return out
    }

    function richDescription(value) {
        var escaped = root.htmlEscape(value)
        var known = [
            "open-meteo.com/en/docs",
            "twelvedata.com/docs",
            "finnhub.io/register",
            "aladhan.com/prayer-times-api",
            "aladhan.com/calculation-methods"
        ]
        var trailingPunctuation = new RegExp("[.,;:!?]+$")
        var httpUrl = new RegExp("https?://[^\\s<]+", "g")

        escaped = escaped.replace(httpUrl, function(match) {
            var clean = match.replace(trailingPunctuation, "")
            var tail = match.slice(clean.length)
            return "<a href=\"" + clean + "\">" + clean + "</a>" + tail
        })

        for (var i = 0; i < known.length; ++i) {
            var label = known[i]
            var href = "https://" + label
            var token = root.escapeRegExp(label)
            var rx = new RegExp("(^|[^\\\"'=/>])(" + token + ")", "g")
            escaped = escaped.replace(rx, function(_, prefix, found) {
                return prefix + "<a href=\"" + href + "\">" + found + "</a>"
            })
        }

        return escaped
    }

    function prayerNameRichText(value) {
        var raw = String(value || "")
        var match = raw.match(/^(.*?)(\s*\([^)]*[\u0600-\u06FF][^)]*\))$/)

        if (!match) {
            return root.htmlEscape(raw)
        }

        var latin = root.htmlEscape(match[1])
        var arabic = root.htmlEscape(match[2])
        return latin + " <span style=\"font-family:'Noto Sans Arabic','Noto Sans','DejaVu Sans','Sans Serif'; font-weight:400;\">" + arabic + "</span>"
    }

    function prayerSecondsUntil(p) {
        if (!p || p.epoch === undefined || p.epoch === null) {
            return null
        }

        var epoch = Number(p.epoch)
        if (isNaN(epoch)) {
            return null
        }

        return Math.floor(epoch - (root.nowTick / 1000))
    }

    function prayerIsUpcoming(p) {
        if (!root.prayerUpcomingHighlight) {
            return false
        }

        var seconds = root.prayerSecondsUntil(p)
        if (seconds === null) {
            return false
        }

        // Mark shortly before the time. Once the time arrives, the separate
        // "now" marker below takes over briefly. This is intentionally a
        // lightweight hint, not a constantly refreshed prayer clock.
        return seconds > 0 && seconds <= 45 * 60
    }

    function prayerIsNow(p) {
        if (!root.prayerUpcomingHighlight) {
            return false
        }

        var seconds = root.prayerSecondsUntil(p)
        if (seconds === null) {
            return false
        }

        // Keep a stronger "Now" marker for about one minute after the time.
        // nowTick updates every 10 seconds, so this clears without a cache refresh.
        return seconds <= 0 && seconds >= -60
    }

    function weatherTemperatureNumber(value) {
        var temp = Number(value)

        if (isNaN(temp)) {
            return null
        }

        return temp
    }

    function weatherTemperatureText(w) {
        var temp = root.weatherTemperatureNumber(w ? w.temperature : undefined)

        if (temp === null) {
            return ""
        }

        var rounded = Math.round(temp * 10) / 10
        return String(rounded) + " °C"
    }

    function weatherTempColor(value) {
        var temp = root.weatherTemperatureNumber(value)

        if (temp === null) {
            return Kirigami.Theme.textColor
        }

        if (temp < 0) {
            return "#5fa8ff"
        }

        if (temp >= 35) {
            return "#ff4d4d"
        }

        if (temp >= 30) {
            return "#ff7a45"
        }

        if (temp >= 25) {
            return "#f0b94d"
        }

        return Kirigami.Theme.textColor
    }

    function weatherLocalTime(w) {
        if (!w) {
            return ""
        }

        var offsetSeconds = Number(w.utc_offset_seconds)

        if (!isNaN(offsetSeconds)) {
            var d = new Date(root.nowTick + offsetSeconds * 1000)
            return root.twoDigits(d.getUTCHours()) + ":" + root.twoDigits(d.getUTCMinutes())
        }

        return w.local_time ? String(w.local_time) : ""
    }

    function weatherDetailParts(w) {
        if (!w || !w.details) {
            return []
        }

        var raw = String(w.details).split(" · ")
        var parts = []
        for (var i = 0; i < raw.length; i++) {
            var part = String(raw[i]).trim()
            if (part.length === 0) {
                continue
            }
            // Keep the weather line readable: Open-Meteo often reports 0.0 mm
            // for rain/snow. Showing that for every city is technically true,
            // but visually noisy. Tiny values that round to 0.0 are skipped too.
            if (/^(Rain|Regen|Snow|Schnee)\s+0(?:[.,]0+)?\s*mm$/i.test(part)) {
                continue
            }
            if (/^(Wind|Gusts|Böen)\s+0(?:[.,]0+)?\s*km\/h$/i.test(part)) {
                continue
            }
            parts.push(part)
        }
        return parts
    }


    function ninaHasWarnings() {
        return root.showNina && root.rssData.nina && root.rssData.nina.items && root.rssData.nina.items.length > 0
    }

    function ninaSeverityLevel(warning) {
        if (!warning || !warning.severity) {
            return 1
        }

        var severity = String(warning.severity).toLowerCase()

        if (severity.indexOf("extreme") >= 0) {
            return 4
        }
        if (severity.indexOf("severe") >= 0) {
            return 3
        }
        if (severity.indexOf("moderate") >= 0) {
            return 2
        }

        return 1
    }

    function ninaAccentColor(warning) {
        return root.ninaSeverityLevel(warning) >= 3 ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.neutralTextColor
    }

    // ---- Compact-view helpers (panel mode) ----------------------------------
    // The panel has almost no space, so these functions build short summary
    // strings.  They tolerate missing data gracefully — every branch checks
    // for the data it needs before touching it.

    function ninaWarningCount() {
        if (!root.showNina || !root.rssData.nina || !root.rssData.nina.items) {
            return 0
        }
        return root.rssData.nina.items.length
    }

    function ninaMaxSeverity() {
        // Returns the highest severity level among current warnings (1-4).
        // Used to colour the panel badge: ≥3 → negative colour, else neutral.
        var max = 0
        if (!root.showNina || !root.rssData.nina || !root.rssData.nina.items) {
            return max
        }
        var items = root.rssData.nina.items
        for (var i = 0; i < items.length; i++) {
            var level = root.ninaSeverityLevel(items[i])
            if (level > max) {
                max = level
            }
        }
        return max
    }

    function firstWeatherSummary() {
        if (!root.showWeather || !root.rssData.weather || !root.rssData.weather.items) {
            return ""
        }
        var items = root.rssData.weather.items
        if (items.length === 0) {
            return ""
        }
        var w = items[0]
        var temp = root.weatherTemperatureText(w)
        var name = w.name || ""
        var condition = w.condition || ""
        var parts = []
        if (name) parts.push(name)
        if (temp) parts.push(temp)
        if (condition) parts.push(condition)
        return parts.join(" · ")
    }

    function firstIndexSummary() {
        if (!root.showMarkets || !root.showMarketIndices) return ""
        if (!root.rssData.markets || !root.rssData.markets.indices) return ""
        var items = root.rssData.markets.indices.items || []
        if (items.length === 0) return ""
        var idx = items[0]
        var name = idx.name || idx.symbol || "Index"
        var value = idx.value || ""
        var pct = idx.change_percent || ""
        var out = name
        if (value) out += " " + value
        if (pct) out += " (" + pct + ")"
        return out
    }

    function firstHeadlineSummary() {
        if (!root.showNews || !root.rssData.feeds) return ""
        var feeds = root.rssData.feeds
        for (var i = 0; i < feeds.length; i++) {
            var f = feeds[i]
            if (f.items && f.items.length > 0 && f.items[0].title) {
                var name = f.name || "Feed"
                return name + ": " + f.items[0].title
            }
        }
        return ""
    }

    function ninaSummary() {
        // Returns a single compact string about active warnings, or "" if none.
        var count = root.ninaWarningCount()
        if (count === 0) {
            return ""
        }
        if (count === 1 && root.rssData.nina.items[0].title) {
            return "⚠ " + String(root.rssData.nina.items[0].title)
        }
        if (root.isEnglish()) {
            return "⚠ " + count + (count === 1 ? " warning" : " warnings")
        }
        return "⚠ " + count + (count === 1 ? " Warnmeldung" : " Warnmeldungen")
    }

    function panelTooltipText() {
        // Multi-line tooltip for icon mode.  Each summary on its own line.
        var lines = []
        var nina = root.ninaSummary()
        if (nina) lines.push(nina)
        var weather = root.firstWeatherSummary()
        if (weather) lines.push(weather)
        var idx = root.firstIndexSummary()
        if (idx) lines.push(idx)
        var headline = root.firstHeadlineSummary()
        if (headline) lines.push(headline)
        if (lines.length === 0) {
            return root.t("noCache")
        }
        return lines.join("\n")
    }

    function marketValueColor(value) {
        var text = String(value || "")

        if (text.charAt(0) === "-") {
            return Kirigami.Theme.negativeTextColor
        }

        if (text.charAt(0) === "+") {
            return Kirigami.Theme.positiveTextColor
        }

        return Kirigami.Theme.textColor
    }

    function marketShortDate(dateText) {
        var text = String(dateText || "").trim()
        var match = text.match(/^(\d{4})-(\d{2})-(\d{2})$/)
        if (match) {
            return match[3] + "." + match[2] + "."
        }
        return text
    }

    function marketTimezoneLabel(item) {
        var abbr = String(item && item.timezone_abbreviation ? item.timezone_abbreviation : "").trim()
        if (abbr) {
            return abbr
        }
        var zone = String(item && item.timezone ? item.timezone : "").trim()
        if (!zone) {
            return ""
        }
        if (zone.indexOf("/") >= 0) {
            var parts = zone.split("/")
            zone = parts[parts.length - 1].replace(/_/g, " ")
        }
        return zone
    }

    function localIsoDateToday() {
        var d = new Date(root.nowTick)
        return d.getFullYear() + "-" + root.twoDigits(d.getMonth() + 1) + "-" + root.twoDigits(d.getDate())
    }


    function marketTimestampLabel(item) {
        if (!item) {
            return ""
        }

        var rawDate = String(item.date || "").trim()
        var localDate = String(item.local_date || rawDate).trim()
        var dateText = root.marketShortDate(rawDate)
        var timeText = String(item.time || "").trim()
        var tzText = root.marketTimezoneLabel(item)
        var showDate = rawDate && (!localDate || localDate !== root.localIsoDateToday())
        var showTimezone = tzText && item.local_timezone !== true
        var out = ""

        // Keep same-day local-market values compact.  DAX in Berlin becomes
        // "13:56"; yesterday's Dow close becomes "14.05. 16:00 EDT"; a same-day
        // foreign exchange keeps its timezone, e.g. "15:30 JST".
        if (showDate && dateText && timeText) {
            out = dateText + " " + timeText
        } else if (showDate && dateText) {
            out = dateText
        } else if (timeText) {
            out = timeText
        } else if (dateText) {
            out = dateText
        }

        if (out && showTimezone) {
            out += " " + tzText
        }
        return out
    }

    function systemValueColor(sys) {
        if (!sys || sys.key !== "vpn") {
            return Kirigami.Theme.textColor
        }
        if (sys.state === "active") {
            return Kirigami.Theme.positiveTextColor
        }
        if (sys.state === "unknown") {
            return Kirigami.Theme.negativeTextColor
        }
        return root.appHighlightColor
    }

    function systemTileOpacity(sys) {
        if (!sys || sys.key !== "vpn") {
            return 0.045
        }
        return sys.state === "unknown" ? 0.12 : 0.10
    }

    function systemItems() {
        if (!root.rssData || !root.rssData.system || !root.rssData.system.items) {
            return []
        }
        return root.rssData.system.items
    }

    function hasSystemContent() {
        return Boolean(root.showSystem && root.systemItems().length > 0)
    }

    function marketSectionItems(key) {
        if (!root.rssData || !root.rssData.markets || !root.rssData.markets[key] || !root.rssData.markets[key].items) {
            return []
        }
        return root.rssData.markets[key].items
    }

    function showMarketSection(key) {
        if (!root.showMarkets) {
            return false
        }
        if (key === "exchange" && !root.showMarketCurrencies) {
            return false
        }
        if (key === "indices" && !root.showMarketIndices) {
            return false
        }
        if (key === "stocks" && !root.showMarketStocks) {
            return false
        }
        return root.marketSectionItems(key).length > 0
    }


    function hasAnyMarketContent() {
        return Boolean(root.showMarkets && (root.showMarketSection("exchange") || root.showMarketSection("indices") || root.showMarketSection("stocks") || (root.rssData && root.rssData.markets && root.rssData.markets.errors && root.rssData.markets.errors.length > 0)))
    }

    function parseCurrenciesText(text) {
        var raw = String(text || "").split(/[\s,;]+/)
        var out = []

        for (var i = 0; i < raw.length; i++) {
            var code = raw[i].trim().toUpperCase()
            if (code.length === 3 && code !== "EUR" && out.indexOf(code) < 0) {
                out.push(code)
            }
        }

        return out
    }

    function addNinaFilters(obj, parts, includeIndex, excludeIndex) {
        if (parts.length > includeIndex && parts[includeIndex].trim().length > 0) {
            obj["include"] = parts[includeIndex].trim()
        }
        if (parts.length > excludeIndex && parts[excludeIndex].trim().length > 0) {
            obj["exclude"] = parts[excludeIndex].trim()
        }
        return obj
    }

    function warningFilterSuffix(entry) {
        var suffix = ""
        if (entry.include || entry.filter || entry.match || entry.exclude || entry.hide) {
            suffix += "|" + (entry.include || entry.filter || entry.match || "")
            suffix += "|" + (entry.exclude || entry.hide || "")
        }
        return suffix
    }

    function parseConfigText(text, kind) {
        var normalized = String(text || "").replace(/\r\n/g, "\n").replace(/\r/g, "\n")
        var lines = normalized.split("\n")
        var out = []

        for (var i = 0; i < lines.length; i++) {
            var line = lines[i].trim()

            if (!line || line.charAt(0) === "#") {
                continue
            }

            var parts = line.split("|")

            if (kind === "feed" && parts.length >= 2) {
                out.push({
                    "name": parts[0].trim(),
                    "url": parts[1].trim(),
                    "limit": parts.length >= 3 ? parseInt(parts[2].trim()) || 5 : 5
                })
            } else if (kind === "weather" && parts.length >= 3) {
                out.push({
                    "name": parts[0].trim(),
                    "lat": parseFloat(parts[1].trim()),
                    "lon": parseFloat(parts[2].trim())
                })
            } else if (kind === "nina" && parts.length >= 2) {
                var sourceToken = parts[0].trim().toLowerCase()
                if ((sourceToken === "de" || sourceToken === "nina" || sourceToken === "bbk") && parts.length >= 3) {
                    out.push(root.addNinaFilters({ "source": "nina", "name": parts[1].trim(), "code": parts[2].trim() }, parts, 3, 4))
                } else if ((sourceToken === "geosphere" || sourceToken === "zamg" || sourceToken === "at" || sourceToken === "austria") && parts.length >= 4) {
                    out.push(root.addNinaFilters({ "source": "geosphere", "name": parts[1].trim(), "lat": parseFloat(parts[2].trim()), "lon": parseFloat(parts[3].trim()) }, parts, 4, 5))
                } else if ((sourceToken === "meteoalarm" || sourceToken === "eu" || sourceToken === "europe") && parts.length >= 3) {
                    out.push(root.addNinaFilters({ "source": "meteoalarm", "name": parts[1].trim(), "country": parts[2].trim() }, parts, 3, 4))
                } else if ((sourceToken === "nws" || sourceToken === "us" || sourceToken === "usa") && parts.length >= 4) {
                    out.push(root.addNinaFilters({ "source": "nws", "name": parts[1].trim(), "lat": parseFloat(parts[2].trim()), "lon": parseFloat(parts[3].trim()) }, parts, 4, 5))
                } else if ((sourceToken === "url" || sourceToken === "feed" || sourceToken === "atom" || sourceToken === "rss") && parts.length >= 3) {
                    out.push(root.addNinaFilters({ "source": "url", "name": parts[1].trim(), "url": parts[2].trim() }, parts, 3, 4))
                } else {
                    out.push(root.addNinaFilters({
                        "source": "nina",
                        "name": parts[0].trim(),
                        "code": parts[1].trim()
                    }, parts, 2, 3))
                }
            } else if (kind === "market" && parts.length >= 2) {
                var marketEntry = {
                    "name": parts[0].trim(),
                    "symbol": parts[1].trim()
                }
                if (parts.length >= 3 && parts[2].trim().length > 0) {
                    marketEntry["display"] = parts[2].trim()
                }
                out.push(marketEntry)
            }
        }

        return out
    }

    function blockEnabled(data, key) {
        if (!data || !data.blocks) {
            return true
        }

        return data.blocks[key] !== false
    }

    function configToText(data) {
        var feeds = []
        var weather = []
        var nina = []
        var markets = []
        var stocks = []

        if (data.feeds) {
            for (var i = 0; i < data.feeds.length; i++) {
                var f = data.feeds[i]
                feeds.push((f.name || "") + "|" + (f.url || "") + "|" + (f.limit || 5))
            }
        }

        if (data.weather_locations) {
            for (var j = 0; j < data.weather_locations.length; j++) {
                var w = data.weather_locations[j]
                weather.push((w.name || "") + "|" + w.lat + "|" + w.lon)
            }
        }

        if (data.nina_codes) {
            for (var k = 0; k < data.nina_codes.length; k++) {
                var n = data.nina_codes[k]
                var src = String(n.source || "nina").toLowerCase()
                if (src === "geosphere" || src === "zamg" || src === "at" || src === "austria") {
                    nina.push("GEOSPHERE|" + (n.name || "") + "|" + (n.lat || "") + "|" + (n.lon || "") + root.warningFilterSuffix(n))
                } else if (src === "meteoalarm") {
                    nina.push("METEOALARM|" + (n.name || "") + "|" + (n.country || n.code || "") + root.warningFilterSuffix(n))
                } else if (src === "nws") {
                    nina.push("NWS|" + (n.name || "") + "|" + (n.lat || "") + "|" + (n.lon || "") + root.warningFilterSuffix(n))
                } else if (src === "url" || src === "feed" || src === "atom" || src === "rss") {
                    nina.push("URL|" + (n.name || "") + "|" + (n.url || "") + root.warningFilterSuffix(n))
                } else {
                    nina.push("NINA|" + (n.name || "") + "|" + (n.code || "") + root.warningFilterSuffix(n))
                }
            }
        }

        if (data.markets && data.markets.indices) {
            for (var m = 0; m < data.markets.indices.length; m++) {
                var market = data.markets.indices[m]
                markets.push((market.name || "") + "|" + (market.symbol || ""))
            }
        }

        if (data.markets && data.markets.stocks) {
            for (var sidx = 0; sidx < data.markets.stocks.length; sidx++) {
                var stock = data.markets.stocks[sidx]
                var stockLine = (stock.name || "") + "|" + (stock.symbol || "")
                if (stock.display || stock.wkn || stock.isin) {
                    stockLine += "|" + (stock.display || stock.wkn || stock.isin)
                }
                stocks.push(stockLine)
            }
        }

        root.feedsText = feeds.join("\n")
        root.weatherText = weather.join("\n")
        root.ninaText = nina.join("\n")
        root.marketsText = markets.join("\n")
        root.stocksText = stocks.join("\n")
        if (data.markets && data.markets.currencies !== undefined) {
            root.currenciesText = Array.isArray(data.markets.currencies) ? data.markets.currencies.join(", ") : String(data.markets.currencies)
        } else {
            root.currenciesText = "USD, GBP, CHF"
        }
        root.twelveDataApiKey = data.markets && data.markets.twelve_data_api_key ? String(data.markets.twelve_data_api_key) : ""
        root.finnhubApiKey = data.markets && data.markets.finnhub_api_key ? String(data.markets.finnhub_api_key) : ""
        root.marketProviderMode = data.markets && data.markets.provider_mode ? String(data.markets.provider_mode) : "auto"
        root.showSystemInfo = !(data.system && data.system.show_info === false)
        root.showSystemNetwork = !(data.system && data.system.show_network === false)
        root.showSystemPublicNetwork = Boolean(data.system && data.system.show_public_network === true)
        root.showSystemVpn = !(data.system && data.system.show_vpn === false)
        root.systemVpnLabel = data.system && data.system.vpn_label ? String(data.system.vpn_label) : ""
        root.showSystemUpdates = !(data.system && data.system.show_updates === false)
        root.showMarketCurrencies = !(data.markets && data.markets.show_currencies === false)
        root.showMarketIndices = !(data.markets && data.markets.show_indices === false)
        root.showMarketStocks = !(data.markets && data.markets.show_stocks === false)

        if (data.prayer) {
            root.prayerCity = data.prayer.city || "Berlin"
            root.prayerCountry = data.prayer.country || "Germany"
            root.prayerMethod = String(data.prayer.method || 3)
        }

        if (data.ui) {
            root.uiFontSize = String(data.ui.font_size || 18)
            root.uiHighlightColor = data.ui.highlight_color ? String(data.ui.highlight_color) : ""
            root.desktopBackgroundMode = root.cleanDesktopBackgroundMode(data.ui.desktop_background_mode || "default")
            root.desktopBackgroundColor = data.ui.desktop_background_color ? String(data.ui.desktop_background_color) : ""
            root.uiLanguage = data.ui.language ? String(data.ui.language) : "de"
            root.newsFontFamily = data.ui.news_font_family ? String(data.ui.news_font_family) : ""
            root.newsFontSizeOffset = String(data.ui.news_font_size_offset !== undefined ? data.ui.news_font_size_offset : 1)
            root.newsFontSize = String(data.ui.news_font_size !== undefined ? data.ui.news_font_size : (root.clampInt(root.uiFontSize, 18, 12, 34) + root.clampInt(root.newsFontSizeOffset, 1, -3, 6)))
            root.newsSyncBaseFontSize = root.baseFontSize
            root.panelMode = data.ui.panel_mode === "warnings" || data.ui.panel_mode === "ticker" ? "warnings" : "icon"
            root.panelIconMode = root.cleanPanelIconMode(data.ui.panel_icon_mode || "dielage")
            root.panelThemeIcon = root.cleanThemeIconName(data.ui.panel_theme_icon || "view-list-details")
            root.panelWarningBadge = data.ui.panel_warning_badge !== false
            root.panelNoWarningsMode = root.cleanPanelNoWarningsMode(data.ui.panel_no_warnings_mode || "icon")
            root.panelWidth = String(data.ui.panel_width !== undefined ? data.ui.panel_width : 24)
            root.panelPopupWidth = String(data.ui.panel_popup_width !== undefined ? data.ui.panel_popup_width : 600)
            root.panelMiddleClickRefresh = data.ui.panel_middle_click_refresh !== false
            root.blockHeadingIcons = data.ui.block_heading_icons !== false
            root.prayerUpcomingHighlight = data.ui.prayer_upcoming_highlight !== false
            root.separatorStyle = root.cleanSeparatorStyle(data.ui.separator_style || "subtle")
            root.newsLinksClickable = data.ui.news_links_clickable !== false
            root.titleStyle = root.cleanTitleStyle(data.ui.title_style || "accent")
            // New in v1.51: optional custom title. Stored as a single string
            // shared between languages, per the user's choice in the picker.
            root.customTitle = data.ui.custom_title ? String(data.ui.custom_title) : ""
        } else if (data.font_size) {
            root.uiFontSize = String(data.font_size)
            root.uiHighlightColor = ""
            root.desktopBackgroundMode = "default"
            root.desktopBackgroundColor = ""
            root.uiLanguage = "de"
            root.newsFontFamily = ""
            root.newsFontSizeOffset = "1"
            root.newsFontSize = String(root.clampInt(root.uiFontSize, 18, 12, 34) + 1)
            root.newsSyncBaseFontSize = root.baseFontSize
            root.panelMode = "icon"
            root.panelIconMode = "dielage"
            root.panelThemeIcon = "view-list-details"
            root.panelWarningBadge = true
            root.panelNoWarningsMode = "icon"
            root.panelWidth = "24"
            root.panelPopupWidth = "600"
            root.panelMiddleClickRefresh = true
            root.blockHeadingIcons = true
            root.prayerUpcomingHighlight = true
            root.separatorStyle = "subtle"
            root.newsLinksClickable = true
            root.titleStyle = "accent"
            root.customTitle = ""
        } else {
            root.uiHighlightColor = ""
            root.desktopBackgroundMode = "default"
            root.desktopBackgroundColor = ""
            root.uiLanguage = "de"
            root.newsFontFamily = ""
            root.newsFontSizeOffset = "1"
            root.newsFontSize = String(root.clampInt(root.uiFontSize, 18, 12, 34) + 1)
            root.newsSyncBaseFontSize = root.baseFontSize
            root.panelMode = "icon"
            root.panelIconMode = "dielage"
            root.panelThemeIcon = "view-list-details"
            root.panelWarningBadge = true
            root.panelNoWarningsMode = "icon"
            root.panelWidth = "24"
            root.panelPopupWidth = "600"
            root.panelMiddleClickRefresh = true
            root.blockHeadingIcons = true
            root.prayerUpcomingHighlight = true
            root.separatorStyle = "subtle"
            root.newsLinksClickable = true
            root.titleStyle = "accent"
            root.customTitle = ""
        }

        root.fetchIntervalMinutes = String(data.fetch_interval_minutes || 10)
        root.localServerPort = String(data.local_server_port || 8765)
        root.bootRefreshEnabled = data.boot_refresh_enabled !== false
        root.bootRefreshDelaySeconds = String(data.boot_refresh_delay_seconds || 120)

        // Block order lives at the top level so older configs that miss it
        // are simply repaired with the default. parseBlockOrder also strips
        // unknown ids and re-appends missing ones, so the array always
        // contains every block exactly once.
        root.blockOrder = root.parseBlockOrder(data.block_order)
        root.collapsedBlocks = root.parseCollapsedBlocks(data.collapsed_blocks)

        root.showWeather = root.blockEnabled(data, "weather")
        root.showPrayer = root.blockEnabled(data, "prayer")
        root.showNina = root.blockEnabled(data, "nina")
        root.showMarkets = root.blockEnabled(data, "markets")
        root.showSystem = root.blockEnabled(data, "system")
        root.showNews = root.blockEnabled(data, "news")

        // Track the freshly-loaded popup width as the "saved" value. Doing this
        // once at the very end of loadConfigData covers every branch (full
        // data.ui, legacy data.font_size, and the empty-data fallback). If we
        // tracked it only inside the data.ui branch, a legacy config followed
        // by Save would falsely detect a width change and close the popup.
        root.savedPanelPopupWidth = root.panelPopupWidthPx()
    }

    function loadCache() {
        var xhr = new XMLHttpRequest()
        root.prepareXhr(xhr, "cache")

        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                if (xhr.status === 200) {
                    try {
                        root.rssData = JSON.parse(xhr.responseText)
                        if (!root.configLoaded && root.rssData.language) {
                            root.uiLanguage = String(root.rssData.language) === "en" ? "en" : "de"
                        }
                        root.errorText = ""
                        root.helperOk = true
                    } catch (e) {
                        root.errorText = root.t("jsonError") + e
                    }
                } else {
                    root.errorText = root.t("cacheUnavailable") + xhr.status
                    // status 0 means the request never reached a server, which is
                    // what happens when the local helper is not running. Anything
                    // else is a real HTTP error and the helper IS responding, so
                    // we do not flip helperOk for those.
                    if (xhr.status === 0) {
                        root.helperOk = false
                        if (!root.portDiscoveryInProgress) {
                            root.discoverLocalHelperPort()
                        }
                    }
                }
                root.initialLoadDone = true
            }
        }

        xhr.open("GET", root.baseUrl + "/rss.json?t=" + Date.now())
        xhr.send()
    }

    function openInternalSettings() {
        root.expanded = true
        root.settingsOpen = true
        root.loadConfig()
    }

    function loadConfig(allowPortDiscovery, afterSuccess) {
        var xhr = new XMLHttpRequest()
        root.prepareXhr(xhr, "config")

        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                if (xhr.status === 200) {
                    try {
                        var data = JSON.parse(xhr.responseText)
                        root.configToText(data)
                        root.configLoaded = true
                        root.errorText = ""
                        root.helperOk = true
                    } catch (e) {
                        root.errorText = root.t("configError") + e
                    }
                    // Always load cache after config so language is already set,
                    // unless a caller needs to chain a refresh first (reset flow).
                    if (typeof afterSuccess === "function") {
                        afterSuccess()
                    } else {
                        root.loadCache()
                    }
                } else {
                    root.errorText = root.t("configUnavailable") + xhr.status
                    if (xhr.status === 0) {
                        root.helperOk = false
                        if (allowPortDiscovery !== false && !root.portDiscoveryInProgress) {
                            root.discoverLocalHelperPort()
                            return
                        }
                    }
                    root.loadCache()
                }
            }
        }

        xhr.open("GET", root.baseUrl + "/config?t=" + Date.now())
        xhr.send()
    }

    function saveConfig() {
        root.saving = true

        // Compute font sizes once; the offset is just (news - base).
        var clampedFontSize = root.clampInt(root.uiFontSize, 18, 12, 34)
        var newsFallback = Math.max(10, clampedFontSize + root.clampInt(root.newsFontSizeOffset, 1, -3, 6))
        var clampedNewsSize = root.clampInt(root.newsFontSize, newsFallback, 10, 42)

        // Normalize panel popup width before saving so the field does not
        // keep stale / invalid text after the POST round-trip. Plasma may cache
        // popup geometry while the popup is open, but the stored setting itself
        // stays deterministic.
        var clampedPanelPopupWidth = root.panelPopupWidthPx()
        var panelPopupWidthChanged = clampedPanelPopupWidth !== root.savedPanelPopupWidth
        root.panelPopupWidth = String(clampedPanelPopupWidth)
        var clampedLocalServerPort = root.clampInt(root.localServerPort, 8765, root.helperPortMin, root.helperPortMax)
        var localServerPortChanged = clampedLocalServerPort !== root.activeServerPort
        root.localServerPort = String(clampedLocalServerPort)

        var payload = {
            "feeds": root.parseConfigText(root.feedsText, "feed"),
            "weather_locations": root.parseConfigText(root.weatherText, "weather"),
            "nina_codes": root.parseConfigText(root.ninaText, "nina"),
            "markets": {
                "currencies": root.parseCurrenciesText(root.currenciesText),
                "indices": root.parseConfigText(root.marketsText, "market"),
                "stocks": root.parseConfigText(root.stocksText, "market"),
                "show_currencies": root.showMarketCurrencies,
                "show_indices": root.showMarketIndices,
                "show_stocks": root.showMarketStocks,
                "provider_mode": root.marketProviderMode,
                "twelve_data_api_key": root.twelveDataApiKey.trim(),
                "finnhub_api_key": root.finnhubApiKey.trim()
            },
            "fetch_interval_minutes": root.clampInt(root.fetchIntervalMinutes, 10, 1, 1440),
            "local_server_port": clampedLocalServerPort,
            "boot_refresh_enabled": root.bootRefreshEnabled,
            "boot_refresh_delay_seconds": root.clampInt(root.bootRefreshDelaySeconds, 120, 10, 1800),
            "system": {
                "show_info": root.showSystemInfo,
                "show_network": root.showSystemNetwork,
                "show_public_network": root.showSystemPublicNetwork,
                "show_vpn": root.showSystemVpn,
                "vpn_label": String(root.systemVpnLabel || "").trim(),
                "show_updates": root.showSystemUpdates
            },
            "ui": {
                "font_size": clampedFontSize,
                "highlight_color": root.validHexColor(root.uiHighlightColor) ? root.normalizedHexColor(root.uiHighlightColor) : "",
                "desktop_background_mode": root.cleanDesktopBackgroundMode(root.desktopBackgroundMode),
                "desktop_background_color": root.validHexColor(root.desktopBackgroundColor) ? root.normalizedHexColor(root.desktopBackgroundColor) : "",
                "language": root.uiLanguage === "en" ? "en" : "de",
                "news_font_family": root.normalizedFontFamily(root.newsFontFamily),
                "news_font_size": clampedNewsSize,
                "news_font_size_offset": clampedNewsSize - clampedFontSize,
                "panel_mode": root.panelMode === "warnings" ? "warnings" : "icon",
                "panel_icon_mode": root.cleanPanelIconMode(root.panelIconMode),
                "panel_theme_icon": root.cleanThemeIconName(root.panelThemeIcon),
                "panel_warning_badge": root.panelWarningBadge,
                "panel_no_warnings_mode": root.cleanPanelNoWarningsMode(root.panelNoWarningsMode),
                "panel_width": root.panelCompactWidthPx(),
                "panel_popup_width": clampedPanelPopupWidth,
                "panel_middle_click_refresh": root.panelMiddleClickRefresh,
                "block_heading_icons": root.blockHeadingIcons,
                "prayer_upcoming_highlight": root.prayerUpcomingHighlight,
                "separator_style": root.cleanSeparatorStyle(root.separatorStyle),
                "news_links_clickable": root.newsLinksClickable,
                "title_style": root.cleanTitleStyle(root.titleStyle),
                "custom_title": String(root.customTitle || "").trim()
            },
            "blocks": {
                "weather": root.showWeather,
                "prayer": root.showPrayer,
                "nina": root.showNina,
                "markets": root.showMarkets,
                "system": root.showSystem,
                "news": root.showNews
            },
            "block_order": root.parseBlockOrder(root.blockOrder),
            "collapsed_blocks": root.collapsedBlocksPayload(),
            "prayer": {
                "city": root.prayerCity.trim() || "Berlin",
                "country": root.prayerCountry.trim() || "Germany",
                "method": root.clampInt(root.prayerMethod, 3, 1, 99)
            }
        }

        var xhr = new XMLHttpRequest()
        root.prepareXhr(xhr)

        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                root.saving = false

                if (xhr.status === 200) {
                    root.savedPanelPopupWidth = clampedPanelPopupWidth
                    root.settingsOpen = false
                    // Plasma often keeps the already-open panel popup geometry.
                    // If only the popup width changed, close the panel popup once so
                    // the next click opens it with the freshly saved width.
                    if (panelPopupWidthChanged && !root.isDesktopApplet()) {
                        root.expanded = false
                    }
                    var serverRestartRequired = localServerPortChanged
                    try {
                        var saveResp = JSON.parse(xhr.responseText || "{}")
                        serverRestartRequired = serverRestartRequired || saveResp.server_restart_required === true
                    } catch (e) {
                        // Older helper response; use local comparison.
                    }
                    if (serverRestartRequired) {
                        root.errorText = root.t("portRestartRequired")
                        return
                    }
                    root.triggerRefresh()
                } else {
                    root.errorText = root.t("saveFailed") + xhr.status
                }
            }
        }

        xhr.open("POST", root.baseUrl + "/config")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.send(JSON.stringify(payload))
    }

    function triggerRefresh() {
        root.refreshing = true

        var xhr = new XMLHttpRequest()
        root.prepareXhr(xhr)

        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                root.refreshing = false

                if (xhr.status === 200) {
                    // The server now answers /refresh with `{ok:true, already_running:true}`
                    // when a refresh from a previous click / the timer is still in flight.
                    // In that case the cache won't be updated yet, so loading it
                    // immediately would just re-display the stale data. Wait a short
                    // moment and try again; the running refresh has a 120 s server-side
                    // timeout, but the typical real run completes in 5–15 s.
                    var alreadyRunning = false
                    try {
                        var resp = JSON.parse(xhr.responseText || "{}")
                        alreadyRunning = resp && resp.already_running === true
                    } catch (e) {
                        // Older servers don't return JSON for /refresh; treat as normal.
                    }
                    if (alreadyRunning) {
                        refreshRetryTimer.restart()
                    } else {
                        root.loadCache()
                    }
                } else {
                    root.errorText = root.t("refreshFailed") + xhr.status
                    if (xhr.status === 0) {
                        root.helperOk = false
                        if (!root.portDiscoveryInProgress) {
                            root.discoverLocalHelperPort()
                        }
                    }
                }
            }
        }

        xhr.open("POST", root.baseUrl + "/refresh")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.send("{}")
    }

    // Fires once after triggerRefresh() saw `already_running:true`. Loads the
    // cache after the in-flight refresh has had time to finish writing rss.json.
    // Five seconds is enough for the common case; if the running refresh takes
    // longer the next regular auto-fetch timer will pick the data up anyway.
    Timer {
        id: refreshRetryTimer
        interval: 5000
        repeat: false
        onTriggered: root.loadCache()
    }

    // ---- Reset everything (v1.51) ------------------------------------------
    // Wipes the local config.json by overwriting with the default file, then
    // re-reads it. The server keeps writing to the same path, so this is a
    // safe round-trip; if the helper is down the user just sees the existing
    // helper-missing screen.
    function resetToDefaults() {
        root.saving = true
        root.resetConfirmVisible = false
        root.helperStatusMessage = ""

        var xhr = new XMLHttpRequest()
        root.prepareXhr(xhr)
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                root.saving = false
                if (xhr.status === 200) {
                    root.errorText = ""
                    root.helperStatusMessage = root.t("resetDefaultsDone")
                    // Re-read the default config first, then rebuild cache once.
                    root.loadConfig(false, function() { root.triggerRefresh() })
                } else {
                    root.errorText = root.t("saveFailed") + xhr.status
                    root.helperStatusMessage = ""
                    if (xhr.status === 0) {
                        root.helperOk = false
                    }
                }
            }
        }
        xhr.open("POST", root.baseUrl + "/reset")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.send("{}")
    }



    function clearCacheOnly() {
        root.cacheClearing = true
        root.helperStatusMessage = ""
        root.showCacheActionMessage(root.t("clearCacheWorking"), true)
        var xhr = new XMLHttpRequest()
        root.prepareXhr(xhr)
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                root.cacheClearing = false
                if (xhr.status === 200) {
                    root.errorText = ""
                    root.helperStatusMessage = root.t("clearCacheDone")
                    root.showCacheActionMessage(root.t("clearCacheDone"), true)
                    root.rssData = root.emptyRssData()
                } else {
                    var failMessage = root.t("clearCacheFailed") + xhr.status
                    root.errorText = failMessage
                    root.helperStatusMessage = ""
                    root.showCacheActionMessage(failMessage, false)
                    if (xhr.status === 0 && !root.portDiscoveryInProgress) {
                        root.helperOk = false
                        root.discoverLocalHelperPort()
                    }
                }
            }
        }
        xhr.open("POST", root.baseUrl + "/clear-cache")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.send("{}")
    }

    function restartLocalService() {
        var preferred = root.clampInt(root.localServerPort, 8765, root.helperPortMin, root.helperPortMax)
        root.pendingServerPort = preferred

        if (!root.helperOk) {
            root.helperStatusMessage = root.t("restartTerminalFallback")
            root.errorText = root.t("restartTerminalFallbackShort")
            root.discoverLocalHelperPort(preferred)
            return
        }

        root.serviceRestarting = true
        var xhr = new XMLHttpRequest()
        root.prepareXhr(xhr)
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                root.serviceRestarting = false
                if (xhr.status === 200) {
                    root.helperOk = false
                    root.errorText = root.t("restartLocalServiceDone")
                    restartDiscoveryTimer.restart()
                } else {
                    root.errorText = root.t("saveFailed") + xhr.status
                    root.helperStatusMessage = root.t("restartTerminalFallback")
                    if (xhr.status === 0) {
                        root.helperOk = false
                        root.discoverLocalHelperPort(preferred)
                    }
                }
            }
        }
        xhr.open("POST", root.baseUrl + "/restart")
        xhr.setRequestHeader("Content-Type", "application/json")
        xhr.send("{}")
    }

    Timer {
        id: restartDiscoveryTimer
        interval: 1800
        repeat: false
        onTriggered: root.discoverLocalHelperPort(root.pendingServerPort)
    }

    Timer {
        id: cacheActionMessageTimer
        interval: 60000
        repeat: false
        onTriggered: root.cacheActionMessage = ""
    }

    function showCacheActionMessage(message, ok) {
        root.cacheActionMessage = message
        root.cacheActionOk = ok
        cacheActionMessageTimer.restart()
    }

    function checkHelperStatus() {
        root.helperStatusChecking = true
        root.helperStatusMessage = root.t("helperStatusChecking")

        var xhr = new XMLHttpRequest()
        root.prepareXhr(xhr, "status")

        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                root.helperStatusChecking = false

                if (xhr.status === 200) {
                    var details = ""
                    try {
                        var data = JSON.parse(xhr.responseText)
                        if (data && data.version) {
                            details = " " + data.version
                        }
                        if (data && data.local_server_port) {
                            details += " · " + root.t("activePortShort") + " " + data.local_server_port
                        }
                    } catch (e) {
                        details = ""
                    }
                    root.helperOk = true
                    root.errorText = ""
                    root.helperStatusMessage = root.t("helperStatusOkChecked") + details
                } else {
                    root.helperOk = false
                    root.helperStatusMessage = root.t("helperStatusMissingChecked") + " (HTTP " + xhr.status + ")"
                    root.errorText = root.t("helperStatusFailed") + xhr.status
                }
            }
        }

        xhr.open("GET", root.baseUrl + "/status?t=" + Date.now())
        xhr.send()
    }

    function toolNames(items, installedOnly) {
        var out = []
        for (var i = 0; i < (items || []).length; i++) {
            var item = items[i] || {}
            if (installedOnly && item.installed !== true) {
                continue
            }
            if (!installedOnly && item.installed === true) {
                continue
            }
            var label = String(item.label || item.id || "").trim()
            if (label.length > 0) {
                out.push(label)
            }
        }
        return out
    }

    function checkRequiredTools() {
        root.toolsStatusChecking = true
        root.toolsStatusOk = true
        root.toolsStatusMessage = root.t("toolsChecking")

        var xhr = new XMLHttpRequest()
        root.prepareXhr(xhr, "status")
        xhr.onreadystatechange = function() {
            if (xhr.readyState === 4) {
                root.toolsStatusChecking = false
                if (xhr.status === 200) {
                    try {
                        var data = JSON.parse(xhr.responseText || "{}")
                        var required = data.required || []
                        var recommended = data.recommended || []
                        var optional = data.optional || []
                        var missingRequired = root.toolNames(required, false)
                        var missingRecommended = root.toolNames(recommended, false)
                        var requiredInstalled = root.toolNames(required, true)
                        var optionalInstalled = root.toolNames(optional, true)

                        if (missingRequired.length === 0) {
                            var msg = root.t("toolsRequiredOk")
                            if (requiredInstalled.length > 0) {
                                msg += "\n" + root.t("toolsRequiredFound") + " " + requiredInstalled.join(", ")
                            }
                            if (missingRecommended.length > 0) {
                                msg += "\n" + root.t("toolsRecommendedMissing") + " " + missingRecommended.join(", ")
                            }
                            if (optionalInstalled.length > 0) {
                                msg += "\n" + root.t("toolsOptionalFound") + " " + optionalInstalled.slice(0, 10).join(", ")
                                if (optionalInstalled.length > 10) {
                                    msg += " +" + String(optionalInstalled.length - 10)
                                }
                            }
                            root.toolsStatusOk = true
                            root.toolsStatusMessage = msg
                        } else {
                            root.toolsStatusOk = false
                            root.toolsStatusMessage = root.t("toolsRequiredMissing") + " " + missingRequired.join(", ") + "\n" + root.t("toolsRequiredHint")
                        }
                    } catch (e) {
                        root.toolsStatusOk = false
                        root.toolsStatusMessage = root.t("toolsCheckFailed") + "parse"
                    }
                } else {
                    root.toolsStatusOk = false
                    root.toolsStatusMessage = root.t("toolsCheckFailed") + xhr.status
                    if (xhr.status === 0 && !root.portDiscoveryInProgress) {
                        root.helperOk = false
                        root.discoverLocalHelperPort()
                    }
                }
            }
        }
        xhr.open("GET", root.baseUrl + "/tools?t=" + Date.now())
        xhr.send()
    }

    Component.onCompleted: {
        // Load config first so uiLanguage is set before the cache result
        // arrives; loadCache() is chained inside loadConfig() to avoid a brief
        // language flip if the cache response wins the race.
        root.loadConfig()
    }

    Timer {
        // Update nowTick every 10 s so weather local-time clocks drift by at
        // most 10 s rather than a full minute.  Overhead is negligible.
        interval: 10000
        running: true
        repeat: true
        onTriggered: root.nowTick = Date.now()
    }

    Timer {
        id: autoFetchTimer
        interval: root.clampInt(root.fetchIntervalMinutes, 10, 1, 1440) * 60000
        running: true
        repeat: true
        onTriggered: root.loadCache()
    }

    Connections {
        target: root
        function onFetchIntervalMinutesChanged() {
            autoFetchTimer.restart()
        }
    }

    // ---- Compact representation (panel mode) --------------------------------
    // Shown when the applet sits in a Plasma panel. Clicking opens the
    // full representation as a popup. Two compact modes exist now:
    // "icon" (local SVG icon + native Plasma tooltip + warning badge) and
    // "warnings" (a tiny status indicator focused only on warnings).
    // The old rotating ticker was removed because panel text gets clipped
    // too aggressively in real-world panel sizes.
    compactRepresentation: Component {
        MouseArea {
            id: compactRoot

            property bool isVertical: Plasmoid.formFactor === PlasmaCore.Types.Vertical
            property int iconSize: Kirigami.Units.iconSizes.smallMedium
            property int panelExtent: root.panelMode === "warnings"
                                      ? Math.max(root.panelCompactWidthPx(), Kirigami.Units.gridUnit * 3)
                                      : root.panelCompactWidthPx()
            implicitWidth: isVertical ? iconSize : panelExtent
            implicitHeight: isVertical ? panelExtent : iconSize
            width: implicitWidth
            height: implicitHeight
            Layout.minimumWidth: implicitWidth
            Layout.preferredWidth: implicitWidth
            Layout.maximumWidth: implicitWidth
            Layout.minimumHeight: implicitHeight
            Layout.preferredHeight: implicitHeight
            Layout.maximumHeight: implicitHeight
            Layout.fillWidth: false
            Layout.fillHeight: false

            hoverEnabled: true
            acceptedButtons: Qt.LeftButton | Qt.MiddleButton
            cursorShape: Qt.PointingHandCursor

            // Left click toggles the popup; middle click forces a refresh.
            onClicked: function(mouse) {
                if (mouse.button === Qt.MiddleButton && root.panelMiddleClickRefresh) {
                    root.triggerRefresh()
                } else {
                    root.expanded = !root.expanded
                }
            }

            // ----- Icon mode ----------------------------------------------------
            Image {
                id: panelIcon
                anchors.fill: parent
                anchors.margins: Math.max(1, Math.round(Kirigami.Units.smallSpacing / 2))
                source: Qt.resolvedUrl("../images/dielage-panel.svg")
                visible: root.panelMode !== "warnings" && root.cleanPanelIconMode(root.panelIconMode) === "dielage"
                fillMode: Image.PreserveAspectFit
                smooth: true
                opacity: compactRoot.containsMouse ? 1.0 : 0.9
            }

            Kirigami.Icon {
                id: panelThemeIconItem
                anchors.fill: parent
                anchors.margins: Math.max(1, Math.round(Kirigami.Units.smallSpacing / 2))
                source: root.effectivePanelThemeIcon()
                visible: root.panelMode !== "warnings" && root.cleanPanelIconMode(root.panelIconMode) === "theme"
                opacity: compactRoot.containsMouse ? 1.0 : 0.9
            }

            // Warning badge: small dot in the corner of the icon when there
            // are active warnings. Red for severe/extreme, neutral otherwise.
            Rectangle {
                visible: root.panelMode !== "warnings" && root.panelWarningBadge && root.ninaWarningCount() > 0
                width: Math.max(9, Math.round(Math.min(compactRoot.width, compactRoot.height) / 2.4))
                height: width
                radius: width / 2
                anchors.right: parent.right
                anchors.bottom: parent.bottom
                anchors.rightMargin: 0
                anchors.bottomMargin: 0
                color: root.ninaMaxSeverity() >= 3
                       ? Kirigami.Theme.negativeTextColor
                       : Kirigami.Theme.neutralTextColor
                border.color: Kirigami.Theme.backgroundColor
                border.width: 1

                PlasmaComponents3.Label {
                    anchors.centerIn: parent
                    visible: parent.width >= 14 && root.ninaWarningCount() < 100
                    text: String(root.ninaWarningCount())
                    color: "white"
                    font.pixelSize: Math.max(8, Math.round(parent.width * 0.68))
                    font.bold: true
                }
            }

            // ----- Warning status mode ----------------------------------------
            Rectangle {
                anchors.fill: parent
                anchors.margins: 1
                visible: root.panelMode === "warnings"
                radius: Math.max(3, Math.round(Kirigami.Units.smallSpacing / 2))
                color: root.ninaWarningCount() > 0
                       ? (root.ninaMaxSeverity() >= 3 ? Qt.rgba(0.9, 0.05, 0.03, 0.22) : Qt.rgba(0.95, 0.65, 0.05, 0.22))
                       : Qt.rgba(0, 0, 0, 0)
                border.color: root.ninaWarningCount() > 0
                              ? (root.ninaMaxSeverity() >= 3 ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.neutralTextColor)
                              : Qt.rgba(0, 0, 0, 0)
                border.width: root.ninaWarningCount() > 0 ? 1 : 0

                Image {
                    anchors.fill: parent
                    anchors.margins: Math.max(1, Math.round(Kirigami.Units.smallSpacing / 2))
                    source: Qt.resolvedUrl("../images/dielage-panel.svg")
                    visible: root.ninaWarningCount() === 0 && root.cleanPanelNoWarningsMode(root.panelNoWarningsMode) === "icon"
                    fillMode: Image.PreserveAspectFit
                    smooth: true
                    opacity: compactRoot.containsMouse ? 1.0 : 0.9
                }

                PlasmaComponents3.Label {
                    anchors.centerIn: parent
                    width: Math.max(1, parent.width - Kirigami.Units.smallSpacing)
                    horizontalAlignment: Text.AlignHCenter
                    verticalAlignment: Text.AlignVCenter
                    text: root.ninaWarningCount() > 0 ? ("⚠ " + root.ninaWarningCount()) : root.panelNoWarningText()
                    visible: root.ninaWarningCount() > 0 || root.cleanPanelNoWarningsMode(root.panelNoWarningsMode) !== "icon"
                    elide: Text.ElideRight
                    color: root.ninaWarningCount() > 0
                           ? (root.ninaMaxSeverity() >= 3 ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.neutralTextColor)
                           : (root.cleanPanelNoWarningsMode(root.panelNoWarningsMode) === "check" ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.disabledTextColor)
                    font.pixelSize: Math.max(10, Kirigami.Units.gridUnit - 3)
                    font.bold: true
                }
            }
        }
    }

    // ---- Full representation (desktop, or panel popup) ----------------------
    fullRepresentation: Component {
        Item {
            id: fullRoot

            // Sensible minimum and preferred sizes.  The desktop user can
            // resize the widget freely, but Plasma will not let them shrink
            // below the minimum.  The popup window also uses these as hints.
            readonly property int targetPopupWidth: root.isDesktopApplet() ? Kirigami.Units.gridUnit * 32 : root.panelPopupWidthPx()
            implicitWidth: targetPopupWidth
            // Do not bind width here. In some Plasma panel setups that leaks
            // back into the compact panel item and stretches the icon area.
            implicitHeight: Kirigami.Units.gridUnit * 47
            Layout.minimumWidth: root.isDesktopApplet() ? Kirigami.Units.gridUnit * 22 : targetPopupWidth
            // In a panel popup Plasma may keep the largest width it has seen
            // unless the full representation also exposes a maximum width.
            // Keep this attached to fullRepresentation only; the compact panel
            // icon has its own strict size hints and must never be stretched.
            Layout.maximumWidth: root.isDesktopApplet() ? 1000000 : targetPopupWidth
            Layout.minimumHeight: Kirigami.Units.gridUnit * 18
            Layout.preferredWidth: targetPopupWidth
            Layout.preferredHeight: Kirigami.Units.gridUnit * 47

            focus: true
            Keys.onEscapePressed: function(event) {
                if (root.settingsOpen) {
                    root.settingsOpen = false
                    event.accepted = true
                }
            }

            Rectangle {
                anchors.fill: parent
                visible: root.useCustomDesktopBackground()
                color: root.normalizedHexColor(root.desktopBackgroundColor)
                radius: Kirigami.Units.largeSpacing
                opacity: 1.0
            }

            ColumnLayout {
                anchors.fill: parent
                anchors.margins: Kirigami.Units.largeSpacing
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true
                    spacing: Kirigami.Units.smallSpacing

                    Rectangle {
                        visible: root.titleAccentVisible()
                        Layout.preferredWidth: 4
                        Layout.preferredHeight: titleColumn.implicitHeight
                        radius: 2
                        color: root.appHighlightColor
                        opacity: 0.95
                    }

                    ColumnLayout {
                        id: titleColumn
                        Layout.fillWidth: true
                        spacing: 0

                        PlasmaComponents3.Label {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: root.displayTitle()
                            font.bold: true
                            font.pixelSize: root.titlePixelSize()
                            color: root.titleColor()
                            elide: Text.ElideRight
                        }

                        PlasmaComponents3.Label {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            visible: root.cleanTitleStyle(root.titleStyle) !== "compact"
                            text: root.rssData.updated ? (root.t("updated") + root.rssData.updated) : root.t("noCache")
                            opacity: 0.72
                            font.pixelSize: root.smallSize
                            elide: Text.ElideRight
                        }
                    }

                    QQC2.Button {
                        text: root.refreshing ? root.t("loading") : root.t("refresh")
                        enabled: !root.refreshing
                        font.pixelSize: root.smallSize
                        QQC2.ToolTip.visible: hovered
                        QQC2.ToolTip.delay: 600
                        QQC2.ToolTip.text: root.t("refresh")
                        onClicked: root.triggerRefresh()
                    }

                    QQC2.Button {
                        text: root.settingsOpen ? root.t("back") : root.t("settings")
                        font.pixelSize: root.smallSize
                        QQC2.ToolTip.visible: hovered
                        QQC2.ToolTip.delay: 600
                        QQC2.ToolTip.text: root.settingsOpen ? root.t("back") : root.t("settings")
                        onClicked: {
                            root.settingsOpen = !root.settingsOpen
                            if (root.settingsOpen) {
                                root.loadConfig()
                            }
                        }
                    }
                }

                PlasmaComponents3.Label {
                    visible: root.cleanTitleStyle(root.titleStyle) === "compact"
                    Layout.fillWidth: true
                    text: root.rssData.updated ? (root.t("updated") + root.rssData.updated) : root.t("noCache")
                    opacity: 0.72
                    font.pixelSize: root.smallSize
                    wrapMode: Text.WordWrap
                    elide: Text.ElideNone
                }

        PlasmaComponents3.Label {
            visible: root.errorText.length > 0
            Layout.fillWidth: true
            text: root.errorText
            color: Kirigami.Theme.negativeTextColor
            font.pixelSize: root.smallSize
            wrapMode: Text.WordWrap
            elide: Text.ElideNone
        }

        Loader {
            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.topMargin: root.settingsOpen ? 0 : Math.round(Kirigami.Units.smallSpacing * 1.6)
            active: true
            // Three-way routing: settings dialog wins over everything; if the
            // helper service is unreachable AND we have already tried to load
            // at least once, show the setup-needed screen; otherwise the
            // normal news view. The initialLoadDone check prevents flashing
            // the setup screen for a split second during the very first XHR.
            sourceComponent: root.settingsOpen
                             ? settingsComponent
                             : (!root.helperOk && root.initialLoadDone)
                                 ? helperMissingComponent
                                 : newsComponent
        }
            }   // end ColumnLayout (full representation)
        }       // end Item fullRoot
    }           // end fullRepresentation: Component

    Component {
        id: settingsComponent

        Item {
            id: settingsRoot
            anchors.fill: parent

            ColumnLayout {
                anchors.fill: parent
                spacing: Kirigami.Units.smallSpacing

                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0

                    PlasmaComponents3.Label {
                        text: root.t("settingsTitle")
                        font.bold: true
                        font.pixelSize: root.sectionSize
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                    }

                    QQC2.Button {
                        text: root.saving ? root.t("saving") : root.t("save")
                        enabled: !root.saving
                        font.pixelSize: root.smallSize
                        onClicked: root.saveConfig()
                    }

                    QQC2.Button {
                        text: root.t("cancel")
                        font.pixelSize: root.smallSize
                        onClicked: root.settingsOpen = false
                    }
                }

                Rectangle {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    height: 1
                    color: Kirigami.Theme.textColor
                    opacity: 0.14
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.minimumWidth: 0
                    Layout.fillHeight: true
                    spacing: Kirigami.Units.largeSpacing

                    QQC2.ScrollView {
                        Layout.preferredWidth: Math.min(Math.max(Kirigami.Units.gridUnit * 9, 150), Math.max(160, settingsRoot.width * 0.30))
                        Layout.fillHeight: true
                        clip: true
                        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

                        ColumnLayout {
                            id: settingsTabsColumn
                            width: Math.max(Kirigami.Units.gridUnit * 8, 140)
                            spacing: Kirigami.Units.smallSpacing

                            Repeater {
                                model: root.settingsTabIds

                                delegate: QQC2.Button {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.settingsTabLabel(modelData)
                                    checkable: true
                                    checked: root.settingsTab === modelData
                                    font.pixelSize: root.smallSize
                                    display: QQC2.AbstractButton.TextOnly
                                    onClicked: root.settingsTab = modelData
                                }
                            }

                            Item { Layout.fillHeight: true }
                        }
                    }

                    Rectangle {
                        Layout.fillHeight: true
                        Layout.preferredWidth: 1
                        color: Kirigami.Theme.textColor
                        opacity: 0.12
                    }

                    QQC2.ScrollView {
                        id: settingsScroll
                        clip: true
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.fillHeight: true
                        contentWidth: Math.max(1, availableWidth)
                        contentHeight: settingsColumn.implicitHeight
                        QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AlwaysOff

                        ColumnLayout {
                            id: settingsColumn
                            width: Math.max(1, settingsScroll.availableWidth - Kirigami.Units.largeSpacing)
                            spacing: Kirigami.Units.largeSpacing * 1.15

                            ColumnLayout {
                                visible: root.settingsTab === "general"
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: Kirigami.Units.largeSpacing

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("generalSettings")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("generalHelp")
                                    opacity: 0.72
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        text: root.t("language")
                                        font.pixelSize: root.smallSize
                                    }

                                    QQC2.ComboBox {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        Layout.maximumWidth: 260
                                        model: ["Deutsch", "English"]
                                        currentIndex: root.uiLanguage === "en" ? 1 : 0
                                        font.pixelSize: root.smallSize
                                        onActivated: function(index) { root.uiLanguage = index === 1 ? "en" : "de" }
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        text: root.t("customTitle")
                                        font.bold: true
                                        font.pixelSize: root.smallSize
                                    }

                                    QQC2.TextField {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.customTitle
                                        font.pixelSize: root.smallSize
                                        placeholderText: root.t("customTitlePlaceholder")
                                        onTextChanged: root.customTitle = text
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("customTitleHelp")
                                        opacity: 0.72
                                        font.pixelSize: root.smallSize
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: Kirigami.Units.largeSpacing

                                        ColumnLayout {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            spacing: Kirigami.Units.smallSpacing

                                            PlasmaComponents3.Label {
                                                text: root.t("titleStyle")
                                                font.pixelSize: root.smallSize
                                            }

                                            QQC2.ComboBox {
                                                Layout.preferredWidth: 280
                                                model: [root.t("titleStyleAccent"), root.t("titleStylePlain"), root.t("titleStyleCompact")]
                                                currentIndex: root.cleanTitleStyle(root.titleStyle) === "plain" ? 1 : (root.cleanTitleStyle(root.titleStyle) === "compact" ? 2 : 0)
                                                font.pixelSize: root.smallSize
                                                onActivated: function(index) {
                                                    root.titleStyle = index === 1 ? "plain" : (index === 2 ? "compact" : "accent")
                                                }
                                            }
                                        }
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("titleStyleHelp")
                                        opacity: 0.72
                                        font.pixelSize: root.smallSize
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                    }
                                }
                            }

                            ColumnLayout {
                                visible: root.settingsTab === "appearance"
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: Kirigami.Units.largeSpacing

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("appearanceSettings")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("appearanceHelp")
                                    opacity: 0.72
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                PlasmaComponents3.Label {
                                    text: root.t("displayUpdate")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("separators")
                                        font.pixelSize: root.smallSize
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                    }

                                    QQC2.ComboBox {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        Layout.maximumWidth: 360
                                        model: [root.t("separatorSubtle"), root.t("separatorStrong"), root.t("separatorNone")]
                                        currentIndex: root.cleanSeparatorStyle(root.separatorStyle) === "strong" ? 1 : (root.cleanSeparatorStyle(root.separatorStyle) === "none" ? 2 : 0)
                                        font.pixelSize: root.smallSize
                                        onActivated: function(index) {
                                            root.separatorStyle = index === 1 ? "strong" : (index === 2 ? "none" : "subtle")
                                        }
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("separatorHelp")
                                        opacity: 0.72
                                        font.pixelSize: root.smallSize
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                    }
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.largeSpacing

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0

                                        PlasmaComponents3.Label {
                                            text: root.t("fontSize")
                                            font.pixelSize: root.smallSize
                                        }

                                        QQC2.TextField {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: root.uiFontSize
                                            font.pixelSize: root.smallSize
                                            placeholderText: "18"
                                            inputMethodHints: Qt.ImhDigitsOnly
                                            onTextChanged: root.uiFontSize = text
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0

                                        PlasmaComponents3.Label {
                                            text: root.t("fetchInterval")
                                            font.pixelSize: root.smallSize
                                        }

                                        QQC2.TextField {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: root.fetchIntervalMinutes
                                            font.pixelSize: root.smallSize
                                            placeholderText: "10"
                                            inputMethodHints: Qt.ImhDigitsOnly
                                            onTextChanged: root.fetchIntervalMinutes = text
                                        }
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        text: root.t("newsFontSize")
                                        font.pixelSize: root.smallSize
                                    }

                                    QQC2.TextField {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        Layout.maximumWidth: 260
                                        text: root.newsFontSize
                                        font.pixelSize: root.smallSize
                                        placeholderText: "19"
                                        inputMethodHints: Qt.ImhDigitsOnly
                                        onTextChanged: root.updateNewsFontSizeFromField(text)
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("newsFontSizeHelp")
                                        opacity: 0.72
                                        font.pixelSize: root.smallSize
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                    }
                                }


                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.largeSpacing

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0

                                        PlasmaComponents3.Label {
                                            text: root.t("highlightColor")
                                            font.pixelSize: root.smallSize
                                        }

                                        QQC2.TextField {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: root.uiHighlightColor
                                            font.pixelSize: root.smallSize
                                            placeholderText: root.t("highlightPlaceholder")
                                            onTextChanged: root.uiHighlightColor = text
                                        }

                                        PlasmaComponents3.Label {
                                            visible: root.uiHighlightColor.length > 0 && !root.validHexColor(root.uiHighlightColor)
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: root.t("highlightHelp")
                                            color: Kirigami.Theme.negativeTextColor
                                            opacity: 0.88
                                            font.pixelSize: root.smallSize
                                            wrapMode: Text.WordWrap
                                            elide: Text.ElideNone
                                        }
                                    }

                                    Rectangle {
                                        Layout.preferredWidth: 42
                                        Layout.preferredHeight: 42
                                        radius: 8
                                        color: root.appHighlightColor
                                        opacity: 0.95
                                    }

                                    QQC2.Button {
                                        text: root.t("plasmaColor")
                                        font.pixelSize: root.smallSize
                                        onClicked: root.uiHighlightColor = ""
                                    }
                                }

                                PlasmaComponents3.Label {
                                    Layout.topMargin: Kirigami.Units.largeSpacing * 0.85
                                    text: root.t("desktopAppearance")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("desktopBackgroundHelp")
                                    opacity: 0.78
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.largeSpacing

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: Kirigami.Units.smallSpacing

                                        PlasmaComponents3.Label {
                                            text: root.t("desktopBackgroundMode")
                                            font.pixelSize: root.smallSize
                                        }

                                        QQC2.ComboBox {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            Layout.maximumWidth: 360
                                            model: [root.t("desktopBackgroundDefault"), root.t("desktopBackgroundTransparent"), root.t("desktopBackgroundCustom")]
                                            currentIndex: root.cleanDesktopBackgroundMode(root.desktopBackgroundMode) === "transparent" ? 1 : (root.cleanDesktopBackgroundMode(root.desktopBackgroundMode) === "custom" ? 2 : 0)
                                            font.pixelSize: root.smallSize
                                            onActivated: function(index) {
                                                root.desktopBackgroundMode = index === 1 ? "transparent" : (index === 2 ? "custom" : "default")
                                            }
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: Kirigami.Units.smallSpacing

                                        PlasmaComponents3.Label {
                                            text: root.t("desktopBackgroundColor")
                                            font.pixelSize: root.smallSize
                                        }

                                        QQC2.TextField {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            enabled: root.cleanDesktopBackgroundMode(root.desktopBackgroundMode) === "custom"
                                            text: root.desktopBackgroundColor
                                            font.pixelSize: root.smallSize
                                            placeholderText: root.t("desktopBackgroundPlaceholder")
                                            onTextChanged: root.desktopBackgroundColor = text
                                        }

                                        PlasmaComponents3.Label {
                                            visible: root.cleanDesktopBackgroundMode(root.desktopBackgroundMode) === "custom"
                                                     && root.desktopBackgroundColor.length > 0
                                                     && !root.validHexColor(root.desktopBackgroundColor)
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: root.t("highlightHelp")
                                            color: Kirigami.Theme.negativeTextColor
                                            opacity: 0.88
                                            font.pixelSize: root.smallSize
                                            wrapMode: Text.WordWrap
                                            elide: Text.ElideNone
                                        }
                                    }
                                }

                                PlasmaComponents3.Label {
                                    Layout.topMargin: Kirigami.Units.largeSpacing * 0.85
                                    text: root.t("panelSettings")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("panelHelp")
                                    opacity: 0.78
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        text: root.t("panelMode")
                                        font.pixelSize: root.smallSize
                                    }

                                    QQC2.ComboBox {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        Layout.maximumWidth: 360
                                        model: [root.t("panelModeIcon"), root.t("panelModeWarnings")]
                                        currentIndex: root.panelMode === "warnings" ? 1 : 0
                                        font.pixelSize: root.smallSize
                                        onActivated: function(index) { root.panelMode = index === 1 ? "warnings" : "icon" }
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        text: root.t("panelPopupWidth")
                                        font.pixelSize: root.smallSize
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: Kirigami.Units.largeSpacing

                                        QQC2.TextField {
                                            Layout.preferredWidth: 110
                                            text: root.panelPopupWidth
                                            font.pixelSize: root.smallSize
                                            placeholderText: "600"
                                            inputMethodHints: Qt.ImhDigitsOnly
                                            onTextEdited: root.panelPopupWidth = text
                                            onEditingFinished: root.panelPopupWidth = String(root.panelPopupWidthPx())
                                        }

                                        PlasmaComponents3.Label {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: root.t("panelPopupWidthHelp")
                                            opacity: 0.70
                                            font.pixelSize: Math.max(9, root.smallSize - 1)
                                            wrapMode: Text.WordWrap
                                            elide: Text.ElideNone
                                        }
                                    }
                                }

                                QQC2.CheckBox {
                                    text: root.t("panelMiddleClickRefresh")
                                    checked: root.panelMiddleClickRefresh
                                    font.pixelSize: root.smallSize
                                    onToggled: root.panelMiddleClickRefresh = checked
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("panelMiddleClickRefreshHelp")
                                    opacity: 0.70
                                    font.pixelSize: Math.max(9, root.smallSize - 1)
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                PlasmaComponents3.Label {
                                    Layout.topMargin: Kirigami.Units.largeSpacing * 0.85
                                    text: root.t("panelIconSettings")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("panelIconHelp")
                                    opacity: 0.78
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.largeSpacing

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: Kirigami.Units.smallSpacing

                                        PlasmaComponents3.Label {
                                            text: root.t("panelIconMode")
                                            font.pixelSize: root.smallSize
                                        }

                                        QQC2.ComboBox {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            Layout.maximumWidth: 360
                                            model: [root.t("panelIconDielage"), root.t("panelIconTheme")]
                                            currentIndex: root.cleanPanelIconMode(root.panelIconMode) === "theme" ? 1 : 0
                                            font.pixelSize: root.smallSize
                                            onActivated: function(index) { root.panelIconMode = index === 1 ? "theme" : "dielage" }
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: Kirigami.Units.smallSpacing
                                        visible: root.cleanPanelIconMode(root.panelIconMode) === "theme"

                                        PlasmaComponents3.Label {
                                            text: root.t("panelIconPreset")
                                            font.pixelSize: root.smallSize
                                        }

                                        QQC2.ComboBox {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            Layout.maximumWidth: 420
                                            model: root.panelThemeIconPresetLabels()
                                            currentIndex: root.panelThemeIconPresetIndex()
                                            font.pixelSize: root.smallSize
                                            onActivated: function(index) {
                                                if (index >= 0 && index < root.panelThemeIconPresetNames.length) {
                                                    root.panelThemeIcon = root.panelThemeIconPresetNames[index]
                                                }
                                            }
                                        }
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing
                                    visible: root.cleanPanelIconMode(root.panelIconMode) === "theme"

                                    PlasmaComponents3.Label {
                                        text: root.t("panelIconName")
                                        font.pixelSize: root.smallSize
                                    }

                                    QQC2.TextField {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.panelThemeIcon
                                        font.pixelSize: root.smallSize
                                        placeholderText: "view-list-details"
                                        onTextChanged: root.panelThemeIcon = text
                                    }
                                }

                                QQC2.CheckBox {
                                    visible: root.panelMode !== "warnings"
                                    Layout.topMargin: Kirigami.Units.smallSpacing
                                    text: root.t("panelWarningBadge")
                                    checked: root.panelWarningBadge
                                    font.pixelSize: root.smallSize
                                    onToggled: root.panelWarningBadge = checked
                                }

                                ColumnLayout {
                                    visible: root.panelMode === "warnings"
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        text: root.t("panelNoWarningsDisplay")
                                        font.pixelSize: root.smallSize
                                    }

                                    QQC2.ComboBox {
                                        Layout.preferredWidth: 280
                                        model: [root.t("panelNoWarningsIcon"), root.t("panelNoWarningsCheck"), root.t("panelNoWarningsDot"), root.t("panelNoWarningsEmpty")]
                                        currentIndex: {
                                            var mode = root.cleanPanelNoWarningsMode(root.panelNoWarningsMode)
                                            if (mode === "check") return 1
                                            if (mode === "dot") return 2
                                            if (mode === "empty") return 3
                                            return 0
                                        }
                                        font.pixelSize: root.smallSize
                                        onActivated: function(index) {
                                            root.panelNoWarningsMode = index === 1 ? "check" : (index === 2 ? "dot" : (index === 3 ? "empty" : "icon"))
                                        }
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("panelNoWarningsHelp")
                                        opacity: 0.70
                                        font.pixelSize: Math.max(9, root.smallSize - 1)
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                    }
                                }

                                QQC2.CheckBox {
                                    Layout.topMargin: Kirigami.Units.largeSpacing * 0.85
                                    text: root.t("blockHeadingIcons")
                                    checked: root.blockHeadingIcons
                                    font.pixelSize: root.smallSize
                                    onToggled: root.blockHeadingIcons = checked
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("blockHeadingIconsHelp")
                                    opacity: 0.70
                                    font.pixelSize: Math.max(9, root.smallSize - 1)
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                PlasmaComponents3.Label {
                                    Layout.topMargin: Kirigami.Units.largeSpacing * 0.85
                                    text: root.t("newsFont")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        text: root.t("newsFontFamily")
                                        font.pixelSize: root.smallSize
                                    }

                                    QQC2.TextField {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.newsFontFamily
                                        font.pixelSize: root.smallSize
                                        placeholderText: root.uiLanguage === "en" ? "empty = Plasma default, e.g. Atkinson Hyperlegible, Inter, Noto Serif" : "leer = Plasma-Standard, z. B. Atkinson Hyperlegible, Inter, Noto Serif"
                                        onTextChanged: root.newsFontFamily = text
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("newsFontFamilyHint")
                                        opacity: 0.72
                                        font.pixelSize: root.smallSize
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                    }
                                }

                                Item {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    implicitHeight: previewLabel.implicitHeight + Kirigami.Units.largeSpacing

                                    Rectangle {
                                        anchors.fill: parent
                                        radius: Kirigami.Units.smallSpacing
                                        color: Kirigami.Theme.textColor
                                        opacity: 0.08
                                    }

                                    PlasmaComponents3.Label {
                                        id: previewLabel
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.leftMargin: Kirigami.Units.smallSpacing
                                        anchors.rightMargin: Kirigami.Units.smallSpacing
                                        text: root.t("preview")
                                        font.pixelSize: root.newsBodySize
                                        font.family: root.normalizedFontFamily(root.newsFontFamily)
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                        color: Kirigami.Theme.textColor
                                    }
                                }

                                QQC2.CheckBox {
                                    text: root.t("newsLinksClickable")
                                    checked: root.newsLinksClickable
                                    font.pixelSize: root.smallSize
                                    onToggled: root.newsLinksClickable = checked
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("newsLinksHelp")
                                    opacity: 0.72
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }
                            }

                            ColumnLayout {
                                visible: root.settingsTab === "content"
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: Kirigami.Units.largeSpacing

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("contentSettings")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("contentHelp")
                                    opacity: 0.72
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                PlasmaComponents3.Label {
                                    text: root.t("blocks")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                GridLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    columns: root.width >= 680 ? 6 : 2
                                    columnSpacing: Kirigami.Units.largeSpacing
                                    rowSpacing: Kirigami.Units.smallSpacing

                                    QQC2.CheckBox { text: root.t("weather"); checked: root.showWeather; font.pixelSize: root.smallSize; onToggled: root.showWeather = checked }
                                    QQC2.CheckBox { text: root.t("prayer"); checked: root.showPrayer; font.pixelSize: root.smallSize; onToggled: root.showPrayer = checked }
                                    QQC2.CheckBox { text: root.t("nina"); checked: root.showNina; font.pixelSize: root.smallSize; onToggled: root.showNina = checked }
                                    QQC2.CheckBox { text: root.t("markets"); checked: root.showMarkets; font.pixelSize: root.smallSize; onToggled: root.showMarkets = checked }
                                    QQC2.CheckBox { text: root.t("system"); checked: root.showSystem; font.pixelSize: root.smallSize; onToggled: root.showSystem = checked }
                                    QQC2.CheckBox { text: root.t("news"); checked: root.showNews; font.pixelSize: root.smallSize; onToggled: root.showNews = checked }
                                }

                                PlasmaComponents3.Label {
                                    Layout.topMargin: Kirigami.Units.largeSpacing * 0.85
                                    text: root.t("blockOrder")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("blockOrderHelp")
                                    opacity: 0.72
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    Repeater {
                                        model: root.blockOrderModel

                                        delegate: Item {
                                            property string blockId: modelData
                                            property int rowIndex: index
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            implicitHeight: blockRow.implicitHeight + Kirigami.Units.smallSpacing

                                            Rectangle {
                                                anchors.fill: parent
                                                radius: Kirigami.Units.smallSpacing
                                                color: root.appHighlightColor
                                                opacity: 0.05
                                            }

                                            RowLayout {
                                                id: blockRow
                                                anchors.left: parent.left
                                                anchors.right: parent.right
                                                anchors.verticalCenter: parent.verticalCenter
                                                anchors.leftMargin: Kirigami.Units.smallSpacing
                                                anchors.rightMargin: Kirigami.Units.smallSpacing
                                                spacing: Kirigami.Units.smallSpacing

                                                PlasmaComponents3.Label {
                                                    Layout.fillWidth: true
                                                    Layout.minimumWidth: 0
                                                    text: (rowIndex + 1) + ". " + root.blockLabel(blockId)
                                                    font.pixelSize: root.smallSize
                                                    elide: Text.ElideRight
                                                }

                                                QQC2.ToolButton {
                                                    icon.name: "arrow-up"
                                                    text: root.t("moveUp")
                                                    display: QQC2.AbstractButton.IconOnly
                                                    QQC2.ToolTip.text: root.t("moveUp")
                                                    QQC2.ToolTip.visible: hovered
                                                    QQC2.ToolTip.delay: 600
                                                    enabled: rowIndex > 0
                                                    onClicked: root.moveBlockUp(blockId)
                                                }

                                                QQC2.ToolButton {
                                                    icon.name: "arrow-down"
                                                    text: root.t("moveDown")
                                                    display: QQC2.AbstractButton.IconOnly
                                                    QQC2.ToolTip.text: root.t("moveDown")
                                                    QQC2.ToolTip.visible: hovered
                                                    QQC2.ToolTip.delay: 600
                                                    enabled: rowIndex < root.blockOrder.length - 1
                                                    onClicked: root.moveBlockDown(blockId)
                                                }
                                            }
                                        }
                                    }

                                    QQC2.Button {
                                        Layout.alignment: Qt.AlignRight
                                        text: root.t("resetOrder")
                                        icon.name: "edit-undo"
                                        font.pixelSize: root.smallSize
                                        onClicked: root.resetBlockOrder()
                                    }
                                }
                            }

                            ColumnLayout {
                                visible: root.settingsTab === "system"
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: Kirigami.Units.largeSpacing

                                PlasmaComponents3.Label {
                                    text: root.t("systemSettings")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                GridLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    columns: root.width >= 760 ? 3 : 2
                                    columnSpacing: Kirigami.Units.largeSpacing
                                    rowSpacing: Kirigami.Units.smallSpacing

                                    QQC2.CheckBox { text: root.t("showSystemInfo"); checked: root.showSystemInfo; font.pixelSize: root.smallSize; enabled: root.showSystem; onToggled: root.showSystemInfo = checked }
                                    QQC2.CheckBox { text: root.t("showSystemNetwork"); checked: root.showSystemNetwork; font.pixelSize: root.smallSize; enabled: root.showSystem; onToggled: root.showSystemNetwork = checked }
                                    QQC2.CheckBox { text: root.t("showSystemPublicNetwork"); checked: root.showSystemPublicNetwork; font.pixelSize: root.smallSize; enabled: root.showSystem; onToggled: root.showSystemPublicNetwork = checked }
                                    QQC2.CheckBox { text: root.t("showSystemVpn"); checked: root.showSystemVpn; font.pixelSize: root.smallSize; enabled: root.showSystem; onToggled: root.showSystemVpn = checked }
                                    QQC2.CheckBox { text: root.t("showSystemUpdates"); checked: root.showSystemUpdates; font.pixelSize: root.smallSize; enabled: root.showSystem; onToggled: root.showSystemUpdates = checked }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    visible: root.showSystem && root.showSystemVpn
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        text: root.t("vpnLabel")
                                        font.pixelSize: root.smallSize
                                    }

                                    QQC2.TextField {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.systemVpnLabel
                                        font.pixelSize: root.smallSize
                                        placeholderText: root.t("vpnLabelPlaceholder")
                                        onTextChanged: root.systemVpnLabel = text
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("vpnLabelHelp")
                                        opacity: 0.68
                                        font.pixelSize: root.smallSize
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                    }
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("systemHelp")
                                    opacity: 0.72
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }
                            }

                            ColumnLayout {
                                visible: root.settingsTab === "sources"
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: Kirigami.Units.largeSpacing

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("dataSourcesSettings")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("dataSourcesHelp")
                                    opacity: 0.72
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("rssSources")
                                    font.pixelSize: root.smallSize
                                }

                                QQC2.ScrollView {
                                    id: feedsTextScroll
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.preferredHeight: 180
                                    clip: true
                                    QQC2.ScrollBar.vertical.policy: QQC2.ScrollBar.AlwaysOn
                                    QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AsNeeded

                                    QQC2.TextArea {
                                        id: feedsTextArea
                                        width: Math.max(feedsTextScroll.availableWidth, feedsTextArea.contentWidth)
                                        text: root.feedsText
                                        wrapMode: TextEdit.NoWrap
                                        selectByMouse: true
                                        font.pixelSize: root.smallSize
                                        onTextChanged: root.feedsText = text
                                    }
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("weatherPlaces")
                                    font.pixelSize: root.smallSize
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.richDescription(root.t("weatherHelp"))
                                    opacity: 0.72
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                    textFormat: Text.RichText
                                    linkColor: root.appHighlightColor
                                    onLinkActivated: function(link) { root.openExternalUrl(link) }
                                }

                                QQC2.ScrollView {
                                    id: weatherTextScroll
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.preferredHeight: 120
                                    clip: true
                                    QQC2.ScrollBar.vertical.policy: QQC2.ScrollBar.AlwaysOn
                                    QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AsNeeded

                                    QQC2.TextArea {
                                        id: weatherTextArea
                                        width: Math.max(weatherTextScroll.availableWidth, weatherTextArea.contentWidth)
                                        text: root.weatherText
                                        wrapMode: TextEdit.NoWrap
                                        selectByMouse: true
                                        font.pixelSize: root.smallSize
                                        onTextChanged: root.weatherText = text
                                    }
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("ninaAreas")
                                    font.pixelSize: root.smallSize
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.richDescription(root.t("ninaHelp"))
                                    opacity: 0.72
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                    textFormat: Text.RichText
                                    linkColor: root.appHighlightColor
                                    onLinkActivated: function(link) { root.openExternalUrl(link) }
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.richDescription(root.t("ninaInternationalHelp"))
                                    opacity: 0.72
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                    textFormat: Text.RichText
                                    linkColor: root.appHighlightColor
                                    onLinkActivated: function(link) { root.openExternalUrl(link) }
                                }

                                QQC2.ScrollView {
                                    id: ninaTextScroll
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.preferredHeight: 120
                                    clip: true
                                    QQC2.ScrollBar.vertical.policy: QQC2.ScrollBar.AlwaysOn
                                    QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AsNeeded

                                    QQC2.TextArea {
                                        id: ninaTextArea
                                        width: Math.max(ninaTextScroll.availableWidth, ninaTextArea.contentWidth)
                                        placeholderText: root.t("ninaPlaceholder")
                                        text: root.ninaText
                                        wrapMode: TextEdit.NoWrap
                                        selectByMouse: true
                                        font.pixelSize: root.smallSize
                                        onTextChanged: root.ninaText = text
                                    }
                                }
                            }

                            ColumnLayout {
                                visible: root.settingsTab === "markets"
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: Kirigami.Units.largeSpacing

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("marketSettings")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                PlasmaComponents3.Label {
                                    text: root.t("marketSubblocks")
                                    font.bold: true
                                    font.pixelSize: root.smallSize
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.largeSpacing

                                    QQC2.CheckBox { text: root.t("showCurrencies"); checked: root.showMarketCurrencies; font.pixelSize: root.smallSize; onToggled: root.showMarketCurrencies = checked }
                                    QQC2.CheckBox { text: root.t("showIndices"); checked: root.showMarketIndices; font.pixelSize: root.smallSize; onToggled: root.showMarketIndices = checked }
                                    QQC2.CheckBox { text: root.t("showStocks"); checked: root.showMarketStocks; font.pixelSize: root.smallSize; onToggled: root.showMarketStocks = checked }
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("emptyMarketHint")
                                    opacity: 0.72
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("currenciesHelp")
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                QQC2.TextField {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.currenciesText
                                    font.pixelSize: root.smallSize
                                    placeholderText: "USD, GBP, CHF"
                                    onTextChanged: root.currenciesText = text
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("indicesHelp")
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                QQC2.ScrollView {
                                    id: marketsTextScroll
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.preferredHeight: 110
                                    clip: true
                                    QQC2.ScrollBar.vertical.policy: QQC2.ScrollBar.AlwaysOn
                                    QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AsNeeded

                                    QQC2.TextArea {
                                        id: marketsTextArea
                                        width: Math.max(marketsTextScroll.availableWidth, marketsTextArea.contentWidth)
                                        text: root.marketsText
                                        wrapMode: TextEdit.NoWrap
                                        selectByMouse: true
                                        font.pixelSize: root.smallSize
                                        onTextChanged: root.marketsText = text
                                    }
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("stocksHelp")
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                QQC2.ScrollView {
                                    id: stocksTextScroll
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.preferredHeight: 100
                                    clip: true
                                    QQC2.ScrollBar.vertical.policy: QQC2.ScrollBar.AlwaysOn
                                    QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AsNeeded

                                    QQC2.TextArea {
                                        id: stocksTextArea
                                        width: Math.max(stocksTextScroll.availableWidth, stocksTextArea.contentWidth)
                                        text: root.stocksText
                                        wrapMode: TextEdit.NoWrap
                                        selectByMouse: true
                                        font.pixelSize: root.smallSize
                                        onTextChanged: root.stocksText = text
                                    }
                                }

                                PlasmaComponents3.Label {
                                    text: root.t("providerMode")
                                    font.pixelSize: root.smallSize
                                }

                                QQC2.ComboBox {
                                    Layout.preferredWidth: 220
                                    model: ["auto", "yahoo", "twelve", "finnhub"]
                                    currentIndex: root.marketProviderMode === "yahoo" ? 1 : (root.marketProviderMode === "twelve" ? 2 : (root.marketProviderMode === "finnhub" ? 3 : 0))
                                    font.pixelSize: root.smallSize
                                    onActivated: function(index) { root.marketProviderMode = index === 1 ? "yahoo" : (index === 2 ? "twelve" : (index === 3 ? "finnhub" : "auto")) }
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.richDescription(root.t("providerHint"))
                                    opacity: 0.72
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                    textFormat: Text.RichText
                                    linkColor: root.appHighlightColor
                                    onLinkActivated: function(link) { root.openExternalUrl(link) }
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.richDescription(root.t("twelveKey"))
                                    opacity: 0.78
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                    textFormat: Text.RichText
                                    linkColor: root.appHighlightColor
                                    onLinkActivated: function(link) { root.openExternalUrl(link) }
                                }

                                QQC2.TextField {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.twelveDataApiKey
                                    echoMode: TextInput.Password
                                    font.pixelSize: root.smallSize
                                    placeholderText: "optional"
                                    onTextChanged: root.twelveDataApiKey = text
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.richDescription(root.t("finnhubKey"))
                                    opacity: 0.78
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                    textFormat: Text.RichText
                                    linkColor: root.appHighlightColor
                                    onLinkActivated: function(link) { root.openExternalUrl(link) }
                                }

                                QQC2.TextField {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.finnhubApiKey
                                    echoMode: TextInput.Password
                                    font.pixelSize: root.smallSize
                                    placeholderText: "optional"
                                    onTextChanged: root.finnhubApiKey = text
                                }
                            }

                            ColumnLayout {
                                visible: root.settingsTab === "prayer"
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: Kirigami.Units.largeSpacing

                                PlasmaComponents3.Label {
                                    text: root.t("prayerSettings")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.richDescription(root.t("prayerHelp"))
                                    opacity: 0.78
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                    textFormat: Text.RichText
                                    linkColor: root.appHighlightColor
                                    onLinkActivated: function(link) { root.openExternalUrl(link) }
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.richDescription(root.t("methodHelp"))
                                    opacity: 0.72
                                    font.pixelSize: root.smallSize
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                    textFormat: Text.RichText
                                    linkColor: root.appHighlightColor
                                    onLinkActivated: function(link) { root.openExternalUrl(link) }
                                }

                                QQC2.CheckBox {
                                    text: root.t("prayerHighlightUpcoming")
                                    checked: root.prayerUpcomingHighlight
                                    font.pixelSize: root.smallSize
                                    onToggled: root.prayerUpcomingHighlight = checked
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("prayerHighlightUpcomingHelp")
                                    opacity: 0.70
                                    font.pixelSize: Math.max(9, root.smallSize - 1)
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.largeSpacing

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0

                                        PlasmaComponents3.Label {
                                            text: root.t("city")
                                            font.pixelSize: root.smallSize
                                        }

                                        QQC2.TextField {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: root.prayerCity
                                            font.pixelSize: root.smallSize
                                            placeholderText: "Berlin"
                                            onTextChanged: root.prayerCity = text
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0

                                        PlasmaComponents3.Label {
                                            text: root.t("country")
                                            font.pixelSize: root.smallSize
                                        }

                                        QQC2.TextField {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: root.prayerCountry
                                            font.pixelSize: root.smallSize
                                            placeholderText: "Germany"
                                            onTextChanged: root.prayerCountry = text
                                        }
                                    }

                                    ColumnLayout {
                                        Layout.preferredWidth: 130

                                        PlasmaComponents3.Label {
                                            text: root.t("method")
                                            font.pixelSize: root.smallSize
                                        }

                                        QQC2.TextField {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: root.prayerMethod
                                            font.pixelSize: root.smallSize
                                            placeholderText: "3"
                                            inputMethodHints: Qt.ImhDigitsOnly
                                            onTextChanged: root.prayerMethod = text
                                        }
                                    }
                                }
                            }

                            ColumnLayout {
                                visible: root.settingsTab === "about"
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: Kirigami.Units.largeSpacing

                                PlasmaComponents3.Label {
                                    text: root.t("aboutSection")
                                    font.bold: true
                                    font.pixelSize: root.sectionSize
                                    opacity: 0.85
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("aboutStoryTitle")
                                    font.bold: true
                                    font.pixelSize: Math.max(10, root.smallSize - 1)
                                    opacity: 0.78
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("aboutStoryText")
                                    opacity: 0.72
                                    font.pixelSize: Math.max(9, root.smallSize - 2)
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.topMargin: Kirigami.Units.smallSpacing
                                    Layout.bottomMargin: Kirigami.Units.smallSpacing
                                    height: 1
                                    color: Kirigami.Theme.textColor
                                    opacity: 0.10
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.helperOk ? root.t("aboutHelperOk") : root.t("aboutHelperMissing")
                                    color: root.helperOk ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.neutralTextColor
                                    opacity: 0.78
                                    font.pixelSize: Math.max(9, root.smallSize - 2)
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.helperOk ? root.t("helperServiceHelpOk") : root.t("helperServiceHelpMissing")
                                    opacity: 0.68
                                    font.pixelSize: Math.max(9, root.smallSize - 2)
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }


                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    QQC2.CheckBox {
                                        text: root.t("bootRefreshEnabled")
                                        checked: root.bootRefreshEnabled
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                        onToggled: root.bootRefreshEnabled = checked
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("bootRefreshDelay")
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                        opacity: root.bootRefreshEnabled ? 1.0 : 0.55
                                        wrapMode: Text.WordWrap
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: Kirigami.Units.smallSpacing

                                        QQC2.TextField {
                                            Layout.preferredWidth: 150
                                            Layout.maximumWidth: 190
                                            text: root.bootRefreshDelaySeconds
                                            font.pixelSize: Math.max(9, root.smallSize - 2)
                                            placeholderText: "120"
                                            inputMethodHints: Qt.ImhDigitsOnly
                                            enabled: root.bootRefreshEnabled
                                            onTextChanged: root.bootRefreshDelaySeconds = text
                                        }

                                        PlasmaComponents3.Label {
                                            text: root.t("secondsUnit")
                                            opacity: root.bootRefreshEnabled ? 0.75 : 0.45
                                            font.pixelSize: Math.max(9, root.smallSize - 2)
                                        }

                                        Item { Layout.fillWidth: true }
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("bootRefreshDelayHelp")
                                        opacity: 0.72
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                    }
                                }



                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("localServerPort")
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                        wrapMode: Text.WordWrap
                                    }

                                    RowLayout {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        spacing: Kirigami.Units.smallSpacing

                                        QQC2.TextField {
                                            Layout.preferredWidth: 150
                                            Layout.maximumWidth: 190
                                            text: root.localServerPort
                                            font.pixelSize: Math.max(9, root.smallSize - 2)
                                            placeholderText: "8765"
                                            inputMethodHints: Qt.ImhDigitsOnly
                                            onTextChanged: root.localServerPort = text
                                        }

                                        PlasmaComponents3.Label {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: root.t("localServerPortConfigured") + ": " + root.localServerPort + " · " + root.t("localServerPortActive") + ": " + root.activeServerPort
                                            color: root.clampInt(root.localServerPort, 8765, root.helperPortMin, root.helperPortMax) === root.activeServerPort ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.neutralTextColor
                                            font.pixelSize: Math.max(9, root.smallSize - 2)
                                            wrapMode: Text.WordWrap
                                            elide: Text.ElideNone
                                        }
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("localServerPortHelp")
                                        opacity: 0.72
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                    }
                                }

                                QQC2.ScrollView {
                                    id: helperCommandsScroll
                                    visible: !root.helperOk
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.preferredHeight: 96
                                    clip: true
                                    QQC2.ScrollBar.vertical.policy: QQC2.ScrollBar.AsNeeded
                                    QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AsNeeded

                                    QQC2.TextArea {
                                        width: helperCommandsScroll.availableWidth
                                        text: root.t("helperServiceCommands")
                                        readOnly: true
                                        selectByMouse: true
                                        wrapMode: Text.WrapAnywhere
                                        font.family: "monospace"
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                    }
                                }

                                Flow {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    QQC2.Button {
                                        text: root.helperStatusChecking ? root.t("loading") : root.t("checkHelperStatus")
                                        icon.name: "view-refresh"
                                        enabled: !root.helperStatusChecking
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                        onClicked: root.checkHelperStatus()
                                    }

                                    QQC2.Button {
                                        text: root.serviceRestarting ? root.t("restarting") : root.t("restartLocalService")
                                        icon.name: "system-reboot"
                                        enabled: !root.serviceRestarting
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                        onClicked: root.restartLocalService()
                                    }

                                    QQC2.Button {
                                        text: root.cacheClearing ? root.t("loading") : root.t("clearCache")
                                        icon.name: "edit-clear-history"
                                        enabled: !root.cacheClearing
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                        onClicked: root.clearCacheOnly()
                                    }

                                    QQC2.Button {
                                        text: root.toolsStatusChecking ? root.t("loading") : root.t("checkTools")
                                        icon.name: "system-search"
                                        enabled: !root.toolsStatusChecking && root.helperOk
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                        onClicked: root.checkRequiredTools()
                                    }

                                    QQC2.Button {
                                        text: root.t("resetDefaults")
                                        icon.name: "edit-clear"
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                        onClicked: root.resetConfirmVisible = true
                                    }

                                    QQC2.Button {
                                        text: root.t("contactAuthor")
                                        icon.name: "mail-message-new"
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                        onClicked: root.openExternalUrl("https://drissner.media/kontakt")
                                    }

                                    QQC2.Button {
                                        text: root.t("donate")
                                        icon.name: "emblem-favorite"
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                        onClicked: root.openExternalUrl("https://www.paypal.me/drissner")
                                    }
                                }

                                Rectangle {
                                    visible: root.cacheActionMessage.length > 0
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    color: Kirigami.Theme.backgroundColor
                                    border.color: root.cacheActionOk ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor
                                    border.width: 1
                                    radius: 6
                                    opacity: 0.98
                                    implicitHeight: cacheActionMessageLabel.implicitHeight + Kirigami.Units.largeSpacing * 2

                                    PlasmaComponents3.Label {
                                        id: cacheActionMessageLabel
                                        anchors.fill: parent
                                        anchors.margins: Kirigami.Units.largeSpacing
                                        text: root.cacheActionMessage
                                        color: root.cacheActionOk ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                    }
                                }

                                Rectangle {
                                    visible: root.toolsStatusMessage.length > 0
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    color: Kirigami.Theme.backgroundColor
                                    border.color: root.toolsStatusOk ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor
                                    border.width: 1
                                    radius: 6
                                    opacity: 0.98
                                    implicitHeight: toolsStatusMessageLabel.implicitHeight + Kirigami.Units.largeSpacing * 2

                                    PlasmaComponents3.Label {
                                        id: toolsStatusMessageLabel
                                        anchors.fill: parent
                                        anchors.margins: Kirigami.Units.largeSpacing
                                        text: root.toolsStatusMessage
                                        color: root.toolsStatusOk ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                    }
                                }

                                Rectangle {
                                    visible: root.resetConfirmVisible
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    color: Kirigami.Theme.backgroundColor
                                    border.color: Kirigami.Theme.neutralTextColor
                                    border.width: 1
                                    radius: 6
                                    opacity: 0.98
                                    implicitHeight: resetConfirmBox.implicitHeight + Kirigami.Units.largeSpacing * 2

                                    ColumnLayout {
                                        id: resetConfirmBox
                                        anchors.fill: parent
                                        anchors.margins: Kirigami.Units.largeSpacing
                                        spacing: Kirigami.Units.smallSpacing

                                        PlasmaComponents3.Label {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: root.t("resetConfirm")
                                            wrapMode: Text.WordWrap
                                            font.pixelSize: Math.max(9, root.smallSize - 2)
                                            opacity: 0.88
                                        }

                                        RowLayout {
                                            Layout.fillWidth: true
                                            spacing: Kirigami.Units.smallSpacing
                                            Item { Layout.fillWidth: true }
                                            QQC2.Button {
                                                text: root.t("resetConfirmNo")
                                                font.pixelSize: Math.max(9, root.smallSize - 2)
                                                onClicked: root.resetConfirmVisible = false
                                            }
                                            QQC2.Button {
                                                text: root.saving ? root.t("saving") : root.t("resetConfirmYes")
                                                icon.name: "edit-clear-history"
                                                enabled: !root.saving
                                                font.pixelSize: Math.max(9, root.smallSize - 2)
                                                onClicked: root.resetToDefaults()
                                            }
                                        }
                                    }
                                }

                                PlasmaComponents3.Label {
                                    visible: root.helperStatusMessage.length > 0
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.helperStatusMessage
                                    color: root.helperOk ? Kirigami.Theme.positiveTextColor : Kirigami.Theme.negativeTextColor
                                    opacity: 0.86
                                    font.pixelSize: Math.max(9, root.smallSize - 2)
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                QQC2.ScrollView {
                                    id: helperStatusCommandsScroll
                                    visible: root.helperStatusMessage.length > 0 && !root.helperOk
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.preferredHeight: 96
                                    clip: true
                                    QQC2.ScrollBar.vertical.policy: QQC2.ScrollBar.AsNeeded
                                    QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AsNeeded

                                    QQC2.TextArea {
                                        width: helperStatusCommandsScroll.availableWidth
                                        text: root.t("helperServiceCommands")
                                        readOnly: true
                                        selectByMouse: true
                                        wrapMode: Text.WrapAnywhere
                                        font.family: "monospace"
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.topMargin: Kirigami.Units.smallSpacing
                                    Layout.bottomMargin: Kirigami.Units.smallSpacing
                                    height: 1
                                    color: Kirigami.Theme.textColor
                                    opacity: 0.10
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("uninstallTitle")
                                    font.bold: true
                                    font.pixelSize: Math.max(10, root.smallSize - 1)
                                    opacity: 0.78
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                PlasmaComponents3.Label {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    text: root.t("uninstallText")
                                    opacity: 0.68
                                    font.pixelSize: Math.max(9, root.smallSize - 2)
                                    wrapMode: Text.WordWrap
                                    elide: Text.ElideNone
                                }

                                QQC2.ScrollView {
                                    id: uninstallCommandsScroll
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.preferredHeight: 96
                                    clip: true
                                    QQC2.ScrollBar.vertical.policy: QQC2.ScrollBar.AsNeeded
                                    QQC2.ScrollBar.horizontal.policy: QQC2.ScrollBar.AsNeeded

                                    QQC2.TextArea {
                                        width: uninstallCommandsScroll.availableWidth
                                        text: root.t("uninstallCommands")
                                        readOnly: true
                                        selectByMouse: true
                                        wrapMode: Text.WrapAnywhere
                                        font.family: "monospace"
                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                    }
                                }

                                ColumnLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.topMargin: Kirigami.Units.smallSpacing
                                    spacing: 0

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("aboutVersion") + " " + root.appVersion
                                        opacity: 0.55
                                        font.pixelSize: Math.max(8, root.smallSize - 4)
                                        horizontalAlignment: Text.AlignLeft
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.t("aboutCopyright")
                                        opacity: 0.48
                                        font.pixelSize: Math.max(8, root.smallSize - 4)
                                        horizontalAlignment: Text.AlignLeft
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }
    }

    Component {
        id: newsComponent

        // // v1.51 NEWS BLOCK ORDERING APPLIED
        QQC2.ScrollView {
            id: scroll
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                width: Math.max(scroll.availableWidth, 340)
                spacing: Kirigami.Units.largeSpacing

                Component {
                    id: weatherBlockComp

                    ColumnLayout {
                        width: Math.max(scroll.availableWidth, 340)
                        spacing: Kirigami.Units.smallSpacing

                        RowLayout {
                            visible: root.showWeather
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: Kirigami.Units.smallSpacing

                            Kirigami.Icon {
                                visible: root.blockHeadingIcons
                                source: root.blockIconName("weather")
                                implicitWidth: Math.max(14, root.sectionSize - 2)
                                implicitHeight: implicitWidth
                                Layout.alignment: Qt.AlignVCenter
                            }

                            PlasmaComponents3.Label {
                                text: root.t("weather")
                                font.bold: true
                                font.pixelSize: root.sectionSize
                                color: root.appHighlightColor
                                wrapMode: Text.WordWrap
                                elide: Text.ElideNone
                            }

                            QQC2.ToolButton {
                                text: "▾"
                                font.pixelSize: Math.max(10, root.smallSize - 1)
                                implicitWidth: Kirigami.Units.gridUnit * 1.25
                                implicitHeight: Kirigami.Units.gridUnit * 1.25
                                QQC2.ToolTip.visible: hovered
                                QQC2.ToolTip.text: root.t("collapseBlock")
                                onClicked: root.toggleBlockCollapsed("weather")
                            }

                            Item { Layout.fillWidth: true }
                        }

                        Repeater {
                            model: root.showWeather && root.rssData.weather && root.rssData.weather.items ? root.rssData.weather.items : []

                            delegate: ColumnLayout {
                                property var w: modelData
                                width: Math.max(scroll.availableWidth, 340)
                                spacing: 2

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        text: w.name || root.t("location")
                                        textFormat: Text.PlainText
                                        font.pixelSize: root.bodySize
                                        font.bold: true
                                        font.italic: true
                                        color: root.appHighlightColor
                                        elide: Text.ElideRight
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: w.condition ? "· " + w.condition : ""
                                        textFormat: Text.PlainText
                                        opacity: 0.92
                                        font.pixelSize: root.bodySize
                                        elide: Text.ElideRight
                                    }

                                    PlasmaComponents3.Label {
                                        text: root.weatherTemperatureText(w)
                                        visible: text.length > 0
                                        font.pixelSize: root.bodySize
                                        font.bold: true
                                        color: root.weatherTempColor(w.temperature)
                                    }

                                    PlasmaComponents3.Label {
                                        property string localClock: root.weatherLocalTime(w)
                                        text: localClock ? "· " + localClock : ""
                                        textFormat: Text.PlainText
                                        visible: text.length > 0
                                        opacity: 0.72
                                        font.pixelSize: root.smallSize
                                        elide: Text.ElideRight
                                    }
                                }

                                Flow {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    width: parent ? parent.width : Math.max(scroll.availableWidth - Kirigami.Units.largeSpacing, 300)
                                    spacing: Kirigami.Units.smallSpacing
                                    visible: root.weatherDetailParts(w).length > 0

                                    Repeater {
                                        model: root.weatherDetailParts(w)

                                        delegate: PlasmaComponents3.Label {
                                            text: (index > 0 ? "· " : "") + String(modelData)
                                            textFormat: Text.PlainText
                                            opacity: 0.78
                                            font.pixelSize: root.smallSize
                                            wrapMode: Text.NoWrap
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Component {
                    id: prayerBlockComp

                    ColumnLayout {
                        width: Math.max(scroll.availableWidth, 340)
                        spacing: Kirigami.Units.smallSpacing

                        RowLayout {
                            visible: root.showPrayer
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: Kirigami.Units.smallSpacing

                            Kirigami.Icon {
                                visible: root.blockHeadingIcons
                                source: root.blockIconName("prayer")
                                implicitWidth: Math.max(14, root.sectionSize - 2)
                                implicitHeight: implicitWidth
                                Layout.alignment: Qt.AlignVCenter
                            }

                            PlasmaComponents3.Label {
                                text: root.t("prayer")
                                font.bold: true
                                font.pixelSize: root.sectionSize
                                color: root.appHighlightColor
                                wrapMode: Text.WordWrap
                                elide: Text.ElideNone
                            }

                            QQC2.ToolButton {
                                text: "▾"
                                font.pixelSize: Math.max(10, root.smallSize - 1)
                                implicitWidth: Kirigami.Units.gridUnit * 1.25
                                implicitHeight: Kirigami.Units.gridUnit * 1.25
                                QQC2.ToolTip.visible: hovered
                                QQC2.ToolTip.text: root.t("collapseBlock")
                                onClicked: root.toggleBlockCollapsed("prayer")
                            }

                            Item { Layout.fillWidth: true }
                        }

                        PlasmaComponents3.Label {
                            visible: root.showPrayer
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: root.rssData.prayer ? ((root.rssData.prayer.location || "") + (root.rssData.prayer.hijri ? " · " + root.rssData.prayer.hijri : "")) : ""
                            opacity: 0.78
                            font.pixelSize: root.smallSize
                            wrapMode: Text.WordWrap
                            elide: Text.ElideNone
                        }

                        GridLayout {
                            visible: root.showPrayer
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            columns: root.prayerColumns
                            columnSpacing: Kirigami.Units.largeSpacing
                            rowSpacing: Kirigami.Units.smallSpacing

                            Repeater {
                                model: root.showPrayer && root.rssData.prayer && root.rssData.prayer.items ? root.rssData.prayer.items : []

                                delegate: Rectangle {
                                    property var p: modelData
                                    property bool nowActive: root.prayerIsNow(p)
                                    property bool upcoming: root.prayerIsUpcoming(p)
                                    property bool marked: nowActive || upcoming
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.preferredWidth: Math.max(150, (scroll.availableWidth - (root.prayerColumns - 1) * Kirigami.Units.largeSpacing) / root.prayerColumns)
                                    implicitHeight: prayerEntry.implicitHeight + (marked ? Kirigami.Units.smallSpacing * 1.4 : 0)
                                    radius: Kirigami.Units.smallSpacing
                                    color: nowActive ? Qt.rgba(1.0, 0.58, 0.18, 0.24) : (upcoming ? Qt.rgba(1.0, 0.58, 0.18, 0.14) : "transparent")
                                    border.width: marked ? 1 : 0
                                    border.color: nowActive ? Kirigami.Theme.positiveTextColor : root.appHighlightColor

                                    ColumnLayout {
                                        id: prayerEntry
                                        anchors.left: parent.left
                                        anchors.right: parent.right
                                        anchors.verticalCenter: parent.verticalCenter
                                        anchors.leftMargin: parent.marked ? Kirigami.Units.smallSpacing : 0
                                        anchors.rightMargin: parent.marked ? Kirigami.Units.smallSpacing : 0
                                        spacing: 0

                                        RowLayout {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            spacing: Kirigami.Units.smallSpacing

                                            PlasmaComponents3.Label {
                                                Layout.fillWidth: true
                                                Layout.minimumWidth: 0
                                                text: root.prayerNameRichText(p.name || "")
                                                textFormat: Text.RichText
                                                font.bold: true
                                                font.pixelSize: root.prayerSize
                                                wrapMode: Text.WordWrap
                                                elide: Text.ElideNone
                                                color: prayerEntry.parent.nowActive ? Kirigami.Theme.positiveTextColor : (prayerEntry.parent.upcoming ? root.appHighlightColor : Kirigami.Theme.textColor)
                                            }

                                            PlasmaComponents3.Label {
                                                visible: prayerEntry.parent.marked
                                                text: prayerEntry.parent.nowActive ? root.t("prayerNowHint") : root.t("prayerUpcomingHint")
                                                color: prayerEntry.parent.nowActive ? Kirigami.Theme.positiveTextColor : root.appHighlightColor
                                                opacity: 0.82
                                                font.pixelSize: Math.max(8, root.prayerSize - 3)
                                                font.bold: true
                                                elide: Text.ElideRight
                                            }
                                        }

                                        PlasmaComponents3.Label {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: (p.time || "") + (p.label ? " · " + p.label : "")
                                            opacity: prayerEntry.parent.marked ? 0.94 : 0.78
                                            color: prayerEntry.parent.nowActive ? Kirigami.Theme.positiveTextColor : (prayerEntry.parent.upcoming ? root.appHighlightColor : Kirigami.Theme.textColor)
                                            font.pixelSize: root.prayerSize
                                            wrapMode: Text.WordWrap
                                            elide: Text.ElideNone
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Component {
                    id: ninaBlockComp

                    ColumnLayout {
                        width: Math.max(scroll.availableWidth, 340)
                        spacing: Kirigami.Units.smallSpacing

                        RowLayout {
                            visible: root.showNina
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: Kirigami.Units.smallSpacing

                            Kirigami.Icon {
                                visible: root.blockHeadingIcons
                                source: root.blockIconName("nina")
                                implicitWidth: Math.max(14, root.sectionSize - 2)
                                implicitHeight: implicitWidth
                                Layout.alignment: Qt.AlignVCenter
                            }

                            PlasmaComponents3.Label {
                                text: root.ninaHasWarnings() ? "⚠ " + root.t("nina") : root.t("nina")
                                font.bold: true
                                font.pixelSize: root.sectionSize
                                color: root.ninaHasWarnings() ? Kirigami.Theme.negativeTextColor : root.appHighlightColor
                                wrapMode: Text.WordWrap
                                elide: Text.ElideNone
                            }

                            QQC2.ToolButton {
                                text: "▾"
                                font.pixelSize: Math.max(10, root.smallSize - 1)
                                implicitWidth: Kirigami.Units.gridUnit * 1.25
                                implicitHeight: Kirigami.Units.gridUnit * 1.25
                                QQC2.ToolTip.visible: hovered
                                QQC2.ToolTip.text: root.t("collapseBlock")
                                onClicked: root.toggleBlockCollapsed("nina")
                            }

                            Item { Layout.fillWidth: true }
                        }

                        PlasmaComponents3.Label {
                            visible: root.ninaHasWarnings()
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: root.t("ninaOfficial")
                            color: Kirigami.Theme.negativeTextColor
                            opacity: 0.88
                            font.pixelSize: root.smallSize
                            wrapMode: Text.WordWrap
                            elide: Text.ElideNone
                        }

                        PlasmaComponents3.Label {
                            visible: Boolean(root.showNina && root.rssData && root.rssData.nina && root.rssData.nina.items && root.rssData.nina.items.length === 0)
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: root.rssData.nina && root.rssData.nina.location ? (root.t("noWarningsFor") + root.rssData.nina.location) : root.t("noWarnings")
                            textFormat: Text.PlainText
                            font.pixelSize: root.bodySize
                            wrapMode: Text.WordWrap
                            elide: Text.ElideNone
                        }

                        Repeater {
                            model: root.showNina && root.rssData.nina && root.rssData.nina.items ? root.rssData.nina.items : []

                            delegate: Item {
                                property var n: modelData
                                property color accentColor: root.ninaAccentColor(n)

                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                width: Math.max(scroll.availableWidth, 340)
                                implicitHeight: warningContent.implicitHeight + Kirigami.Units.largeSpacing

                                Rectangle {
                                    anchors.fill: parent
                                    radius: Kirigami.Units.smallSpacing
                                    color: accentColor
                                    opacity: 0.12
                                }

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.top: parent.top
                                    anchors.bottom: parent.bottom
                                    width: 4
                                    radius: 2
                                    color: accentColor
                                    opacity: 0.95
                                }

                                ColumnLayout {
                                    id: warningContent
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    anchors.leftMargin: Kirigami.Units.largeSpacing
                                    anchors.rightMargin: Kirigami.Units.largeSpacing
                                    spacing: 2

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: "⚠ " + (n.title || root.t("warning"))
                                        textFormat: Text.PlainText
                                        font.pixelSize: root.bodySize
                                        font.bold: true
                                        color: accentColor
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: n.details || ""
                                        textFormat: Text.PlainText
                                        opacity: 0.82
                                        font.pixelSize: root.smallSize
                                        wrapMode: Text.WordWrap
                                        elide: Text.ElideNone
                                    }
                                }
                            }
                        }
                    }
                }

                Component {
                    id: systemBlockComp

                    ColumnLayout {
                        width: Math.max(scroll.availableWidth, 340)
                        spacing: Kirigami.Units.smallSpacing

                        RowLayout {
                            visible: root.hasSystemContent()
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: Kirigami.Units.smallSpacing

                            Kirigami.Icon {
                                visible: root.blockHeadingIcons
                                source: root.blockIconName("system")
                                implicitWidth: Math.max(14, root.sectionSize - 2)
                                implicitHeight: implicitWidth
                                Layout.alignment: Qt.AlignVCenter
                            }

                            PlasmaComponents3.Label {
                                text: root.t("system")
                                font.bold: true
                                font.pixelSize: root.sectionSize
                                color: root.appHighlightColor
                                wrapMode: Text.WordWrap
                                elide: Text.ElideNone
                            }

                            QQC2.ToolButton {
                                text: "▾"
                                font.pixelSize: Math.max(10, root.smallSize - 1)
                                implicitWidth: Kirigami.Units.gridUnit * 1.25
                                implicitHeight: Kirigami.Units.gridUnit * 1.25
                                QQC2.ToolTip.visible: hovered
                                QQC2.ToolTip.text: root.t("collapseBlock")
                                onClicked: root.toggleBlockCollapsed("system")
                            }

                            Item { Layout.fillWidth: true }
                        }

                        GridLayout {
                            visible: root.hasSystemContent()
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            columns: root.width >= 760 ? 3 : (root.width >= 520 ? 2 : 1)
                            columnSpacing: Kirigami.Units.largeSpacing * 1.5
                            rowSpacing: Kirigami.Units.smallSpacing

                            Repeater {
                                model: root.hasSystemContent() ? root.systemItems() : []

                                delegate: Item {
                                    property var sys: modelData
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    Layout.preferredHeight: Math.max(root.smallSize + Kirigami.Units.largeSpacing, 28)

                                    Rectangle {
                                        anchors.fill: parent
                                        radius: Kirigami.Units.smallSpacing
                                        color: sys.key === "vpn" ? root.systemValueColor(sys) : root.appHighlightColor
                                        opacity: root.systemTileOpacity(sys)
                                    }

                                    RowLayout {
                                        anchors.fill: parent
                                        anchors.leftMargin: Kirigami.Units.smallSpacing
                                        anchors.rightMargin: Kirigami.Units.smallSpacing
                                        spacing: Kirigami.Units.smallSpacing

                                        PlasmaComponents3.Label {
                                            text: sys.label || ""
                                            textFormat: Text.PlainText
                                            font.pixelSize: root.smallSize
                                            font.bold: true
                                            color: Kirigami.Theme.textColor
                                            opacity: 0.70
                                            elide: Text.ElideRight
                                            Layout.maximumWidth: parent.width * 0.34
                                        }

                                        Rectangle {
                                            Layout.preferredWidth: 2
                                            Layout.fillHeight: true
                                            Layout.leftMargin: Kirigami.Units.smallSpacing
                                            Layout.rightMargin: Kirigami.Units.smallSpacing
                                            Layout.topMargin: Kirigami.Units.smallSpacing
                                            Layout.bottomMargin: Kirigami.Units.smallSpacing
                                            color: root.appHighlightColor
                                            opacity: 0.58
                                        }

                                        PlasmaComponents3.Label {
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            text: sys.value || "--"
                                            textFormat: Text.PlainText
                                            font.pixelSize: root.smallSize
                                            font.bold: true
                                            color: root.systemValueColor(sys)
                                            elide: Text.ElideRight
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Component {
                    id: marketsBlockComp

                    ColumnLayout {
                        width: Math.max(scroll.availableWidth, 340)
                        spacing: Kirigami.Units.smallSpacing

                        RowLayout {
                            visible: root.hasAnyMarketContent()
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: Kirigami.Units.smallSpacing

                            Kirigami.Icon {
                                visible: root.blockHeadingIcons
                                source: root.blockIconName("markets")
                                implicitWidth: Math.max(14, root.sectionSize - 2)
                                implicitHeight: implicitWidth
                                Layout.alignment: Qt.AlignVCenter
                            }

                            PlasmaComponents3.Label {
                                text: root.t("markets")
                                font.bold: true
                                font.pixelSize: root.sectionSize
                                color: root.appHighlightColor
                                wrapMode: Text.WordWrap
                                elide: Text.ElideNone
                            }

                            QQC2.ToolButton {
                                text: "▾"
                                font.pixelSize: Math.max(10, root.smallSize - 1)
                                implicitWidth: Kirigami.Units.gridUnit * 1.25
                                implicitHeight: Kirigami.Units.gridUnit * 1.25
                                QQC2.ToolTip.visible: hovered
                                QQC2.ToolTip.text: root.t("collapseBlock")
                                onClicked: root.toggleBlockCollapsed("markets")
                            }

                            Item { Layout.fillWidth: true }
                        }

                        PlasmaComponents3.Label {
                            visible: Boolean(root.showMarkets && root.rssData && root.rssData.markets && root.rssData.markets.errors && root.rssData.markets.errors.length > 0)
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: root.rssData.markets.errors ? root.rssData.markets.errors.join(" · ") : ""
                            color: Kirigami.Theme.neutralTextColor
                            font.pixelSize: root.smallSize
                            wrapMode: Text.WordWrap
                            elide: Text.ElideNone
                        }

                        ColumnLayout {
                            visible: root.hasAnyMarketContent()
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: Kirigami.Units.largeSpacing

                            ColumnLayout {
                                visible: root.showMarketSection("exchange")
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: Kirigami.Units.smallSpacing

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        text: root.t("exchangeRates")
                                        font.bold: true
                                        font.pixelSize: root.smallSize
                                        color: root.appHighlightColor
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.rssData.markets && root.rssData.markets.exchange && root.rssData.markets.exchange.date ? ("· " + root.rssData.markets.exchange.source + " · " + root.rssData.markets.exchange.date + (root.rssData.markets.exchange.previous_date ? " vs. " + root.rssData.markets.exchange.previous_date : "")) : ""
                                        visible: text.length > 0
                                        font.pixelSize: root.smallSize
                                        opacity: 0.62
                                        elide: Text.ElideRight
                                    }
                                }

                                GridLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    columns: root.width >= 760 ? 3 : (root.width >= 520 ? 2 : 1)
                                    columnSpacing: Kirigami.Units.largeSpacing * 1.5
                                    rowSpacing: Kirigami.Units.smallSpacing

                                    Repeater {
                                        model: root.showMarketSection("exchange") ? root.marketSectionItems("exchange") : []

                                        delegate: Item {
                                            property var fx: modelData
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            Layout.preferredHeight: Math.max(root.smallSize + Kirigami.Units.largeSpacing, 28)

                                            Rectangle {
                                                anchors.fill: parent
                                                radius: Kirigami.Units.smallSpacing
                                                color: root.appHighlightColor
                                                opacity: 0.045
                                            }

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.leftMargin: Kirigami.Units.smallSpacing
                                                anchors.rightMargin: Kirigami.Units.smallSpacing
                                                spacing: Kirigami.Units.smallSpacing

                                                PlasmaComponents3.Label {
                                                    text: fx.label || ""
                                                    font.pixelSize: root.smallSize
                                                    font.bold: true
                                                    color: Kirigami.Theme.textColor
                                                    opacity: 0.78
                                                    elide: Text.ElideRight
                                                    Layout.maximumWidth: parent.width * 0.42
                                                }

                                                Rectangle {
                                                    Layout.preferredWidth: 2
                                                    Layout.fillHeight: true
                                                    Layout.leftMargin: Kirigami.Units.largeSpacing * 1.2
                                                    Layout.rightMargin: Kirigami.Units.largeSpacing * 1.2
                                                    Layout.topMargin: Kirigami.Units.smallSpacing
                                                    Layout.bottomMargin: Kirigami.Units.smallSpacing
                                                    color: root.appHighlightColor
                                                    opacity: 0.74
                                                }

                                                PlasmaComponents3.Label {
                                                    text: fx.value || "--"
                                                    font.pixelSize: root.smallSize
                                                    font.bold: true
                                                    color: Kirigami.Theme.textColor
                                                }

                                                Item {
                                                    visible: !!fx.change_percent
                                                    Layout.preferredWidth: Kirigami.Units.smallSpacing
                                                }

                                                PlasmaComponents3.Label {
                                                    visible: !!fx.change_percent
                                                    text: fx.change_percent || ""
                                                    font.pixelSize: root.smallSize
                                                    font.bold: true
                                                    color: root.marketValueColor(fx.change_percent)
                                                }

                                                Item { Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }
                            }

                            Item {
                                visible: root.showMarketSection("exchange") && root.showMarketSection("indices")
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Layout.preferredHeight: Kirigami.Units.largeSpacing

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    height: 1
                                    color: Kirigami.Theme.textColor
                                    opacity: 0.18
                                }
                            }

                            ColumnLayout {
                                visible: root.showMarketSection("indices")
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: Kirigami.Units.smallSpacing

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        text: root.t("indices")
                                        font.bold: true
                                        font.pixelSize: root.smallSize
                                        color: root.appHighlightColor
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.rssData.markets && root.rssData.markets.indices && root.rssData.markets.indices.source ? ("· " + root.rssData.markets.indices.source) : ""
                                        visible: text.length > 0
                                        font.pixelSize: root.smallSize
                                        opacity: 0.62
                                        elide: Text.ElideRight
                                    }
                                }

                                GridLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    columns: root.width >= 760 ? 3 : (root.width >= 520 ? 2 : 1)
                                    columnSpacing: Kirigami.Units.largeSpacing * 1.5
                                    rowSpacing: Kirigami.Units.smallSpacing

                                    Repeater {
                                        model: root.showMarketSection("indices") ? root.marketSectionItems("indices") : []

                                        delegate: Item {
                                            property var idx: modelData
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            Layout.preferredHeight: Math.max(root.smallSize * 2 + Kirigami.Units.smallSpacing, 34)

                                            Rectangle {
                                                anchors.fill: parent
                                                radius: Kirigami.Units.smallSpacing
                                                color: root.appHighlightColor
                                                opacity: 0.045
                                            }

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.leftMargin: Kirigami.Units.smallSpacing
                                                anchors.rightMargin: Kirigami.Units.smallSpacing
                                                spacing: Kirigami.Units.smallSpacing

                                                PlasmaComponents3.Label {
                                                    text: idx.name || "Index"
                                                    textFormat: Text.PlainText
                                                    font.pixelSize: root.smallSize
                                                    font.bold: true
                                                    font.italic: true
                                                    color: Kirigami.Theme.textColor
                                                    opacity: 0.80
                                                    elide: Text.ElideRight
                                                    Layout.maximumWidth: parent.width * 0.38
                                                }

                                                Rectangle {
                                                    Layout.preferredWidth: 2
                                                    Layout.fillHeight: true
                                                    Layout.leftMargin: Kirigami.Units.largeSpacing * 1.2
                                                    Layout.rightMargin: Kirigami.Units.largeSpacing * 1.2
                                                    Layout.topMargin: Kirigami.Units.smallSpacing
                                                    Layout.bottomMargin: Kirigami.Units.smallSpacing
                                                    color: root.appHighlightColor
                                                    opacity: 0.74
                                                }

                                                PlasmaComponents3.Label {
                                                    text: idx.value || "--"
                                                    font.pixelSize: root.smallSize
                                                    font.bold: true
                                                    color: Kirigami.Theme.textColor
                                                }

                                                Item {
                                                    visible: !!idx.change_percent
                                                    Layout.preferredWidth: Kirigami.Units.smallSpacing
                                                }

                                                PlasmaComponents3.Label {
                                                    visible: !!idx.change_percent
                                                    text: idx.change_percent || ""
                                                    font.pixelSize: Math.max(9, root.smallSize - 1)
                                                    font.bold: true
                                                    color: root.marketValueColor(idx.change_percent)
                                                }

                                                PlasmaComponents3.Label {
                                                    text: root.marketTimestampLabel(idx)
                                                    visible: text.length > 0
                                                    opacity: 0.58
                                                    font.pixelSize: Math.max(9, root.smallSize - 1)
                                                    elide: Text.ElideRight
                                                }

                                                Item { Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }
                            }

                            Item {
                                visible: root.showMarketSection("stocks") && (root.showMarketSection("exchange") || root.showMarketSection("indices"))
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                Layout.preferredHeight: Kirigami.Units.largeSpacing

                                Rectangle {
                                    anchors.left: parent.left
                                    anchors.right: parent.right
                                    anchors.verticalCenter: parent.verticalCenter
                                    height: 1
                                    color: Kirigami.Theme.textColor
                                    opacity: 0.18
                                }
                            }

                            ColumnLayout {
                                visible: root.showMarketSection("stocks")
                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                spacing: Kirigami.Units.smallSpacing

                                RowLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    PlasmaComponents3.Label {
                                        text: root.t("stocks")
                                        font.bold: true
                                        font.pixelSize: root.smallSize
                                        color: root.appHighlightColor
                                    }

                                    PlasmaComponents3.Label {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        text: root.rssData.markets && root.rssData.markets.stocks && root.rssData.markets.stocks.source ? ("· " + root.rssData.markets.stocks.source) : ""
                                        visible: text.length > 0
                                        font.pixelSize: root.smallSize
                                        opacity: 0.62
                                        elide: Text.ElideRight
                                    }
                                }

                                GridLayout {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    columns: root.width >= 760 ? 3 : (root.width >= 520 ? 2 : 1)
                                    columnSpacing: Kirigami.Units.largeSpacing * 1.5
                                    rowSpacing: Kirigami.Units.smallSpacing

                                    Repeater {
                                        model: root.showMarketSection("stocks") ? root.marketSectionItems("stocks") : []

                                        delegate: Item {
                                            property var idx: modelData
                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            Layout.preferredHeight: Math.max(root.smallSize * 2 + Kirigami.Units.smallSpacing, 34)

                                            Rectangle {
                                                anchors.fill: parent
                                                radius: Kirigami.Units.smallSpacing
                                                color: root.appHighlightColor
                                                opacity: 0.045
                                            }

                                            RowLayout {
                                                anchors.fill: parent
                                                anchors.leftMargin: Kirigami.Units.smallSpacing
                                                anchors.rightMargin: Kirigami.Units.smallSpacing
                                                spacing: Kirigami.Units.smallSpacing

                                                ColumnLayout {
                                                    spacing: 0
                                                    Layout.maximumWidth: parent.width * 0.38

                                                    PlasmaComponents3.Label {
                                                        text: idx.name || idx.display_name || idx.display || "Stock"
                                                        textFormat: Text.PlainText
                                                        font.pixelSize: root.smallSize
                                                        font.bold: true
                                                        font.italic: true
                                                        color: Kirigami.Theme.textColor
                                                        opacity: 0.80
                                                        elide: Text.ElideRight
                                                    }

                                                    PlasmaComponents3.Label {
                                                        visible: !!idx.display && idx.display !== idx.name
                                                        text: idx.display || ""
                                                        font.pixelSize: Math.max(9, root.smallSize - 2)
                                                        color: Kirigami.Theme.textColor
                                                        opacity: 0.52
                                                        elide: Text.ElideRight
                                                    }
                                                }

                                                Rectangle {
                                                    Layout.preferredWidth: 2
                                                    Layout.fillHeight: true
                                                    Layout.leftMargin: Kirigami.Units.largeSpacing * 1.2
                                                    Layout.rightMargin: Kirigami.Units.largeSpacing * 1.2
                                                    Layout.topMargin: Kirigami.Units.smallSpacing
                                                    Layout.bottomMargin: Kirigami.Units.smallSpacing
                                                    color: root.appHighlightColor
                                                    opacity: 0.74
                                                }

                                                PlasmaComponents3.Label {
                                                    text: idx.value || "--"
                                                    font.pixelSize: root.smallSize
                                                    font.bold: true
                                                    color: Kirigami.Theme.textColor
                                                }

                                                Item {
                                                    visible: !!idx.change_percent
                                                    Layout.preferredWidth: Kirigami.Units.smallSpacing
                                                }

                                                PlasmaComponents3.Label {
                                                    visible: !!idx.change_percent
                                                    text: idx.change_percent || ""
                                                    font.pixelSize: Math.max(9, root.smallSize - 1)
                                                    font.bold: true
                                                    color: root.marketValueColor(idx.change_percent)
                                                }

                                                PlasmaComponents3.Label {
                                                    text: root.marketTimestampLabel(idx)
                                                    visible: text.length > 0
                                                    opacity: 0.58
                                                    font.pixelSize: Math.max(9, root.smallSize - 1)
                                                    elide: Text.ElideRight
                                                }

                                                Item { Layout.fillWidth: true }
                                            }
                                        }
                                    }
                                }
                            }
                        }
                    }
                }

                Component {
                    id: newsBlockComp

                    ColumnLayout {
                        width: Math.max(scroll.availableWidth, 340)
                        spacing: Kirigami.Units.smallSpacing

                        // Main block separators are handled by the outer block loader.
                        // Feed-level separators remain below for readability.

                        RowLayout {
                            visible: root.showNews
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            spacing: Kirigami.Units.smallSpacing

                            Kirigami.Icon {
                                visible: root.blockHeadingIcons
                                source: root.blockIconName("news")
                                implicitWidth: Math.max(14, root.sectionSize - 2)
                                implicitHeight: implicitWidth
                                Layout.alignment: Qt.AlignVCenter
                            }

                            PlasmaComponents3.Label {
                                text: root.t("news")
                                font.bold: true
                                font.pixelSize: root.sectionSize
                                color: root.appHighlightColor
                                wrapMode: Text.WordWrap
                                elide: Text.ElideNone
                            }

                            QQC2.ToolButton {
                                text: "▾"
                                font.pixelSize: Math.max(10, root.smallSize - 1)
                                implicitWidth: Kirigami.Units.gridUnit * 1.25
                                implicitHeight: Kirigami.Units.gridUnit * 1.25
                                QQC2.ToolTip.visible: hovered
                                QQC2.ToolTip.text: root.t("collapseBlock")
                                onClicked: root.toggleBlockCollapsed("news")
                            }

                            Item { Layout.fillWidth: true }
                        }

                        PlasmaComponents3.Label {
                            visible: Boolean(root.showNews && root.rssData && root.rssData.errors && root.rssData.errors.length > 0)
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            text: root.rssData.errors ? root.rssData.errors.join(" · ") : ""
                            color: Kirigami.Theme.neutralTextColor
                            font.pixelSize: root.smallSize
                            wrapMode: Text.WordWrap
                            elide: Text.ElideNone
                        }

                        Repeater {
                            model: root.showNews ? (root.rssData.feeds || []) : []

                            delegate: ColumnLayout {
                                property var feed: modelData

                                Layout.fillWidth: true
                                Layout.minimumWidth: 0
                                width: Math.max(scroll.availableWidth, 340)
                                spacing: Kirigami.Units.smallSpacing

                                ColumnLayout {
                                    id: feedColumn
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    spacing: Kirigami.Units.smallSpacing

                                    Item {
                                        Layout.fillWidth: true
                                        Layout.minimumWidth: 0
                                        implicitHeight: Math.max(sourceName.implicitHeight + Kirigami.Units.smallSpacing, root.newsBodySize + Kirigami.Units.smallSpacing * 2)

                                        Rectangle {
                                            anchors.fill: parent
                                            radius: Kirigami.Units.smallSpacing
                                            color: root.appHighlightColor
                                            opacity: 0.10
                                        }

                                        PlasmaComponents3.Label {
                                            id: sourceName
                                            anchors.left: parent.left
                                            anchors.right: parent.right
                                            anchors.verticalCenter: parent.verticalCenter
                                            anchors.leftMargin: Kirigami.Units.smallSpacing
                                            anchors.rightMargin: Kirigami.Units.smallSpacing
                                            text: feed.name || "Feed"
                                            textFormat: Text.PlainText
                                            font.bold: true
                                            font.pixelSize: root.newsBodySize
                                            font.family: root.normalizedFontFamily(root.newsFontFamily)
                                            color: root.appHighlightColor
                                            wrapMode: Text.WordWrap
                                            elide: Text.ElideNone
                                        }
                                    }

                                    Repeater {
                                        model: feed.items || []

                                        delegate: Item {
                                            id: headline
                                            property var entry: modelData
                                            property bool clickable: Boolean(root.newsLinksClickable && headline.entry && headline.entry.link && headline.entry.link.length > 0)

                                            Layout.fillWidth: true
                                            Layout.minimumWidth: 0
                                            Layout.leftMargin: Kirigami.Units.smallSpacing
                                            Layout.rightMargin: Kirigami.Units.smallSpacing
                                            Layout.topMargin: 1
                                            Layout.bottomMargin: 1
                                            implicitHeight: headlineRow.implicitHeight

                                            RowLayout {
                                                id: headlineRow
                                                anchors.left: parent.left
                                                anchors.right: parent.right
                                                anchors.top: parent.top
                                                spacing: Kirigami.Units.smallSpacing

                                                PlasmaComponents3.Label {
                                                    text: "•"
                                                    Layout.alignment: Qt.AlignTop
                                                    Layout.topMargin: Math.max(0, Math.round(root.newsBodySize * 0.08))
                                                    font.pixelSize: root.newsBodySize
                                                    font.family: root.normalizedFontFamily(root.newsFontFamily)
                                                    color: (headline.clickable && clickArea.containsMouse) ? root.appHighlightColor : Kirigami.Theme.textColor
                                                }

                                                PlasmaComponents3.Label {
                                                    id: headlineText
                                                    Layout.fillWidth: true
                                                    Layout.minimumWidth: 0
                                                    text: headline.entry.title || ""
                                                    textFormat: Text.PlainText
                                                    font.pixelSize: root.newsBodySize
                                                    font.family: root.normalizedFontFamily(root.newsFontFamily)
                                                    wrapMode: Text.WordWrap
                                                    elide: Text.ElideNone
                                                    color: (headline.clickable && clickArea.containsMouse) ? root.appHighlightColor : Kirigami.Theme.textColor
                                                }
                                            }

                                            MouseArea {
                                                id: clickArea
                                                anchors.fill: parent
                                                hoverEnabled: true
                                                cursorShape: headline.clickable ? Qt.PointingHandCursor : Qt.ArrowCursor
                                                enabled: headline.clickable
                                                onClicked: root.openExternalUrl(headline.entry.link)
                                            }
                                            // Keyboard navigation: Tab to focus, Enter/Return to open.
                                            activeFocusOnTab: headline.clickable
                                            Keys.onReturnPressed: if (headline.clickable) root.openExternalUrl(headline.entry.link)
                                            Keys.onEnterPressed: if (headline.clickable) root.openExternalUrl(headline.entry.link)
                                        }
                                    }
                                }

                                Rectangle {
                                    Layout.fillWidth: true
                                    Layout.minimumWidth: 0
                                    height: 1
                                    opacity: 0.14
                                    color: Kirigami.Theme.textColor
                                }
                            }
                        }
                    }
                }


                // The order Repeater. Walks root.blockOrder and instantiates
                // the matching Component per entry. parseBlockOrder() guarantees
                // every block appears exactly once. Hidden blocks (toggles in
                // settings) collapse to zero height via their internal visible
                // bindings; the slot still exists so toggling visibility back
                // on cannot reshuffle position.
                Repeater {
                    model: root.blockOrderModel
                    delegate: ColumnLayout {
                        property string blockId: modelData
                        property bool collapsed: root.isBlockCollapsed(blockId)
                        visible: root.isBlockVisible(blockId)
                        Layout.fillWidth: true
                        Layout.minimumWidth: 0
                        Layout.topMargin: root.hasVisibleBlockBefore(blockId) ? Kirigami.Units.largeSpacing : 0
                        spacing: 0

                        Rectangle {
                            visible: root.blockSeparatorVisible(blockId)
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.bottomMargin: Kirigami.Units.smallSpacing
                            height: root.separatorHeight()
                            color: Kirigami.Theme.textColor
                            opacity: root.separatorOpacity()
                        }

                        RowLayout {
                            visible: collapsed
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            Layout.bottomMargin: Kirigami.Units.smallSpacing
                            spacing: Kirigami.Units.smallSpacing

                            Kirigami.Icon {
                                visible: root.blockHeadingIcons
                                source: root.blockIconName(blockId)
                                implicitWidth: Math.max(14, root.sectionSize - 2)
                                implicitHeight: implicitWidth
                                Layout.alignment: Qt.AlignVCenter
                            }

                            PlasmaComponents3.Label {
                                text: root.blockLabel(blockId)
                                font.bold: true
                                font.pixelSize: root.sectionSize
                                color: blockId === "nina" && root.ninaHasWarnings() ? Kirigami.Theme.negativeTextColor : root.appHighlightColor
                                wrapMode: Text.WordWrap
                                elide: Text.ElideNone
                            }

                            QQC2.ToolButton {
                                text: "▸"
                                font.pixelSize: Math.max(10, root.smallSize - 1)
                                implicitWidth: Kirigami.Units.gridUnit * 1.25
                                implicitHeight: Kirigami.Units.gridUnit * 1.25
                                QQC2.ToolTip.visible: hovered
                                QQC2.ToolTip.text: root.t("expandBlock")
                                onClicked: root.toggleBlockCollapsed(blockId)
                            }

                            Item { Layout.fillWidth: true }

                            PlasmaComponents3.Label {
                                text: root.t("collapsedHint")
                                opacity: 0.54
                                font.pixelSize: Math.max(9, root.smallSize - 2)
                                elide: Text.ElideRight
                            }
                        }

                        Loader {
                            Layout.fillWidth: true
                            Layout.minimumWidth: 0
                            visible: !collapsed
                            active: !collapsed
                            sourceComponent:
                                blockId === "weather" ? weatherBlockComp
                                : blockId === "prayer"  ? prayerBlockComp
                                : blockId === "nina"    ? ninaBlockComp
                                : blockId === "system"  ? systemBlockComp
                                : blockId === "markets" ? marketsBlockComp
                                : blockId === "news"    ? newsBlockComp
                                : null
                        }
                    }
                }
            }
        }
    }

    // ---- Helper-missing screen (v1.51) ------------------------------------
    // Shown when the local Python helper service is not reachable. Gives a
    // copy-pasteable setup command and a "Retry" button. The block is QML-
    // only so it works even if the helper has never been installed (which is
    // exactly the KDE Store first-run case).
    Component {
        id: helperMissingComponent

        QQC2.ScrollView {
            id: helperScroll
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                width: Math.max(helperScroll.availableWidth, 320)
                spacing: Kirigami.Units.largeSpacing

                Item {
                    Layout.fillWidth: true
                    Layout.preferredHeight: Kirigami.Units.largeSpacing * 2
                }

                Kirigami.Icon {
                    Layout.alignment: Qt.AlignHCenter
                    Layout.preferredWidth: Kirigami.Units.iconSizes.huge
                    Layout.preferredHeight: Kirigami.Units.iconSizes.huge
                    source: root.effectivePlasmoidIcon()
                    opacity: 0.65
                }

                PlasmaComponents3.Label {
                    Layout.fillWidth: true
                    text: root.t("helperMissingTitle")
                    horizontalAlignment: Text.AlignHCenter
                    font.bold: true
                    font.pixelSize: root.titleSize
                    wrapMode: Text.WordWrap
                    elide: Text.ElideNone
                }

                PlasmaComponents3.Label {
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.largeSpacing
                    Layout.rightMargin: Kirigami.Units.largeSpacing
                    text: root.t("helperMissingBody")
                    wrapMode: Text.WordWrap
                    elide: Text.ElideNone
                    font.pixelSize: root.bodySize
                    opacity: 0.86
                }

                Flow {
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.largeSpacing
                    Layout.rightMargin: Kirigami.Units.largeSpacing
                    spacing: Kirigami.Units.smallSpacing

                    QQC2.Button {
                        text: root.t("downloadInstallerZip")
                        icon.name: "download"
                        font.pixelSize: root.smallSize
                        onClicked: root.openExternalUrl(root.latestInstallerZipUrl)
                    }

                    QQC2.Button {
                        text: root.t("openHomepage")
                        icon.name: "globe"
                        font.pixelSize: root.smallSize
                        onClicked: root.openExternalUrl(root.projectUrl)
                    }

                    QQC2.Button {
                        text: root.t("retryConnection")
                        icon.name: "view-refresh"
                        font.pixelSize: root.smallSize
                        onClicked: root.loadConfig()
                    }
                }

                PlasmaComponents3.Label {
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.largeSpacing
                    Layout.rightMargin: Kirigami.Units.largeSpacing
                    text: root.t("helperMissingHint")
                    wrapMode: Text.WordWrap
                    elide: Text.ElideNone
                    font.pixelSize: root.smallSize
                    opacity: 0.72
                }

                RowLayout {
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.largeSpacing
                    Layout.rightMargin: Kirigami.Units.largeSpacing
                    spacing: Kirigami.Units.smallSpacing

                    Rectangle {
                        Layout.fillWidth: true
                        Layout.preferredHeight: setupCmd.implicitHeight + Kirigami.Units.largeSpacing
                        radius: Kirigami.Units.smallSpacing
                        color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.08)

                        QQC2.TextArea {
                            id: setupCmd
                            anchors.fill: parent
                            anchors.margins: Kirigami.Units.smallSpacing
                            readOnly: true
                            selectByMouse: true
                            wrapMode: TextEdit.Wrap
                            font.family: "monospace"
                            font.pixelSize: root.smallSize
                            text: root.helperInstallCommands()
                            background: null
                        }
                    }

                    QQC2.Button {
                        id: copyButton
                        text: copyButton.copied ? root.t("copied") : root.t("copyCommand")
                        icon.name: copyButton.copied ? "dialog-ok" : "edit-copy"
                        font.pixelSize: root.smallSize
                        property bool copied: false
                        onClicked: {
                            setupCmd.selectAll()
                            setupCmd.copy()
                            copyButton.copied = true
                            copyResetTimer.restart()
                        }

                        Timer {
                            id: copyResetTimer
                            interval: 2000
                            onTriggered: copyButton.copied = false
                        }
                    }
                }

                Item { Layout.fillWidth: true; Layout.fillHeight: true }
            }
        }
    }

}
