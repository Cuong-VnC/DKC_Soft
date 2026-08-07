// --- CONFIG & GLOBAL STATE ---

// Detect API base URL from query params, local storage, or default to HuggingFace Space
const DEFAULT_API_BASE = "https://bhugvh-demobot.hf.space";
const urlParams = new URLSearchParams(window.location.search);
const apiParam = urlParams.get("api");

if (apiParam) {
    localStorage.setItem("dkc_api_base", apiParam);
}

const API_BASE = localStorage.getItem("dkc_api_base") || DEFAULT_API_BASE;
console.log("DKC Backend API Base URL:", API_BASE);

// Resolve WS URL from HTTP URL
const WS_BASE = API_BASE.replace(/^http/, "ws");

// Intercept all fetch requests to automatically add Authorization header if token exists
const originalFetch = window.fetch;
window.fetch = function (url, options) {
    options = options || {};
    const token = localStorage.getItem("dkc_auth_token");
    if (token && url.toString().startsWith(API_BASE)) {
        options.headers = options.headers || {};
        if (options.headers instanceof Headers) {
            options.headers.set("Authorization", `Bearer ${token}`);
        } else if (Array.isArray(options.headers)) {
            const hasAuth = options.headers.some(h => h[0].toLowerCase() === 'authorization');
            if (!hasAuth) {
                options.headers.push(["Authorization", `Bearer ${token}`]);
            }
        } else {
            if (!options.headers["Authorization"]) {
                options.headers["Authorization"] = `Bearer ${token}`;
            }
        }
    }
    return originalFetch(url, options);
};

let edgeVoices = [];
let capcutVoices = [];
let scenes = [];
let logos = [];
let activeJobId = null;
let wsConn = null;
let currentLanguage = "vi";
let selectedLogoIndex = 0;

// Translations matching ui/config.py
const TRANSLATIONS = {
    vi: {
        brand: "AI Drawing Generator",
        scene_label: "Cảnh #",
        preview_ready: "Sẵn sàng.",
        render_success: "🎉 Render thành công!",
        render_failed: "❌ Render thất bại",
        auth_success: "Đăng nhập tự động thành công!",
        auth_loading: "Đang xác thực...",
        confirm_cancel: "Bạn có chắc chắn muốn hủy tiến trình render hiện tại không?",
        alert_no_scenes: "Vui lòng thêm ít nhất một cảnh vẽ (Hình ảnh + Kịch bản).",
        alert_missing_image: "Vui lòng chọn hình ảnh đầu vào đầy đủ cho các cảnh.",
    },
    en: {
        brand: "AI Drawing Generator",
        scene_label: "Scene #",
        preview_ready: "Ready.",
        render_success: "🎉 Render successful!",
        render_failed: "❌ Render failed",
        auth_success: "Automatic authentication successful!",
        auth_loading: "Authenticating...",
        confirm_cancel: "Are you sure you want to cancel the current render process?",
        alert_no_scenes: "Please add at least one scene (Image + Script).",
        alert_missing_image: "Please select a valid image for all scenes.",
    }
};

// --- DOM ELEMENTS CACHE ---
const elements = {
    brandLabel: document.getElementById("lbl-brand"),
    btnToggleTheme: document.getElementById("btn-toggle-theme"),
    
    // Inputs & Settings Controls
    appModeRadios: document.getElementsByName("app-mode"),
    cmbTtsModel: document.getElementById("cmb_tts_model"),
    cmbVoice: document.getElementById("cmb_voice"),
    sldRate: document.getElementById("sld_rate"),
    lblRateVal: document.getElementById("lbl_rate_val"),
    sldPitch: document.getElementById("sld_pitch"),
    lblPitchVal: document.getElementById("lbl_pitch_val"),
    cmbPen: document.getElementById("cmb_pen"),
    btnUploadBrush: document.getElementById("btn_upload_brush"),
    cmbBg: document.getElementById("cmb_bg"),
    btnUploadBg: document.getElementById("btn_upload_bg"),
    pickerColor: document.getElementById("picker_color"),
    frameColorPrev: document.getElementById("frame_color_prev"),
    cmbColorOpt: document.getElementById("cmb_color_opt"),
    cmbDrawDirection: document.getElementById("cmb_draw_direction"),
    sldWidth: document.getElementById("sld_width"),
    lblWidthVal: document.getElementById("lbl_width_val"),
    entryBgm: document.getElementById("entry_bgm"),
    btnBrowseBgm: document.getElementById("btn-browse-bgm"),
    bgmFileInput: document.getElementById("bgm-file-input"),
    sldMvol: document.getElementById("sld_mvol"),
    lblMvolVal: document.getElementById("lbl_mvol_val"),
    sldVvol: document.getElementById("sld_vvol"),
    lblVvolVal: document.getElementById("lbl_vvol_val"),
    cmbColorStyle: document.getElementById("cmb_color_style"),
    swCamera: document.getElementById("sw_camera"),
    swSmartOrder: document.getElementById("sw_smart_order"),
    swSlideTransition: document.getElementById("sw_slide_transition"),
    cmbLogos: document.getElementById("cmb_logos"),
    btnLogoUpload: document.getElementById("btn_logo_upload"),
    btnLogoPos: document.getElementById("btn_logo_pos"),
    btnLogoDel: document.getElementById("btn_logo_del"),
    logoFileInput: document.getElementById("logo-file-input"),
    cmbRes: document.getElementById("cmb_res"),
    cmbFps: document.getElementById("cmb_fps"),
    cmbExportMode: document.getElementById("cmb_export_mode"),
    
    // Storyboard Timeline
    storyboardContainer: document.getElementById("storyboard-container"),
    btnAddScene: document.getElementById("btn-add-scene"),
    btnUploadImages: document.getElementById("btn_upload_images"),
    btnUploadScript: document.getElementById("btn_upload_script"),
    bulkImagesInput: document.getElementById("bulk-images-input"),
    bulkScriptInput: document.getElementById("bulk-script-input"),
    btnLoadProj: document.getElementById("btn_load_proj"),
    btnSaveProj: document.getElementById("btn_save_proj"),
    projectFileInput: document.getElementById("project-file-input"),
    
    // Player Controls & Console
    previewCanvas: document.getElementById("preview-canvas"),
    lblProgress: document.getElementById("lbl_progress"),
    lblEta: document.getElementById("lbl_eta"),
    progressBarChunk: document.getElementById("progress-bar-chunk"),
    btnRender: document.getElementById("btn_render"),
    btnCancel: document.getElementById("btn_cancel"),
    btnPause: document.getElementById("btn_pause"),
    btnResume: document.getElementById("btn_resume"),
    txtLogs: document.getElementById("txt_logs"),
    
    // Logo Position Dialog
    logoModal: document.getElementById("logo-modal"),
    btnCloseLogoModal: document.getElementById("btn-close-logo-modal"),
    cmbActiveDialogLogo: document.getElementById("cmb-active-dialog-logo"),
    logoDragzone: document.getElementById("logo-dragzone"),
    logoScaleSlider: document.getElementById("logo-scale-slider"),
    lblLogoScaleVal: document.getElementById("lbl-logo-scale-val"),
    btnSaveLogoPos: document.getElementById("btn-save-logo-pos"),
    btnCancelLogoPos: document.getElementById("btn-cancel-logo-pos")
};

// Canvas 2D context
const canvasCtx = elements.previewCanvas.getContext("2d");

// --- INITIALIZATION ---
document.addEventListener("DOMContentLoaded", () => {
    initTheme();
    setupEventListeners();
    setupLoginListeners();
    checkAuthStatus();
});

async function checkAuthStatus() {
    const token = localStorage.getItem("dkc_auth_token") || "";
    try {
        const resp = await originalFetch(`${API_BASE}/api/auth/status?token=${token}`);
        const data = await resp.json();
        
        const loginModal = document.getElementById("login-modal");
        if (!loginModal) return;
        
        if (data.auth_required && !data.authenticated) {
            loginModal.classList.add("active");
            return false;
        } else {
            loginModal.classList.remove("active");
            
            // Load application data
            loadAssetsLists();
            loadVoicesList();
            
            return true;
        }
    } catch (e) {
        console.error("Auth status check failed:", e);
        // Fallback to normal loading if API is unreachable
        loadAssetsLists();
        loadVoicesList();
    }
}

function setupLoginListeners() {
    const btnSubmit = document.getElementById("btn-login-submit");
    const txtUser = document.getElementById("login-username");
    const txtPass = document.getElementById("login-password");
    const lblStatus = document.getElementById("auth-status-lbl");
    
    if (!btnSubmit) return;
    
    btnSubmit.addEventListener("click", async () => {
        const username = txtUser.value.trim();
        const password = txtPass.value;
        
        if (!username || !password) {
            lblStatus.className = "error";
            lblStatus.textContent = "Vui lòng nhập đầy đủ tài khoản và mật khẩu!";
            return;
        }
        
        btnSubmit.disabled = true;
        lblStatus.className = "info";
        lblStatus.textContent = "Đang đăng nhập...";
        
        try {
            const resp = await originalFetch(`${API_BASE}/api/auth/login`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({ username, password })
            });
            
            const data = await resp.json();
            btnSubmit.disabled = false;
            
            if (resp.ok && data.success) {
                localStorage.setItem("dkc_auth_token", data.token);
                lblStatus.className = "success";
                lblStatus.textContent = "Đăng nhập thành công!";
                
                setTimeout(() => {
                    checkAuthStatus();
                }, 500);
            } else {
                lblStatus.className = "error";
                lblStatus.textContent = data.detail || "Đăng nhập thất bại!";
            }
        } catch (e) {
            btnSubmit.disabled = false;
            lblStatus.className = "error";
            lblStatus.textContent = "Lỗi kết nối tới máy chủ!";
            console.error(e);
        }
    });
    
    const handleEnter = (e) => {
        if (e.key === "Enter") btnSubmit.click();
    };
    if (txtUser) txtUser.addEventListener("keydown", handleEnter);
    if (txtPass) txtPass.addEventListener("keydown", handleEnter);
}

// --- THEME MANAGEMENT ---
function initTheme() {
    const savedTheme = localStorage.getItem("dkc_theme") || "dark";
    if (savedTheme === "light") {
        document.body.classList.remove("dark-theme");
        document.body.classList.add("light-theme");
    } else {
        document.body.classList.remove("light-theme");
        document.body.classList.add("dark-theme");
    }
}

elements.btnToggleTheme.addEventListener("click", () => {
    if (document.body.classList.contains("dark-theme")) {
        document.body.classList.remove("dark-theme");
        document.body.classList.add("light-theme");
        localStorage.setItem("dkc_theme", "light");
    } else {
        document.body.classList.remove("light-theme");
        document.body.classList.add("dark-theme");
        localStorage.setItem("dkc_theme", "dark");
    }
});



// --- LOAD DROPDOWN ASSETS ---
async function loadAssetsLists() {
    try {
        const resp = await fetch(`${API_BASE}/api/assets`);
        const data = await resp.json();
        
        // Populate backgrounds
        elements.cmbBg.innerHTML = "";
        data.backgrounds.forEach(bg => {
            const opt = document.createElement("option");
            opt.value = bg;
            opt.textContent = bg;
            elements.cmbBg.appendChild(opt);
        });
        
        // Populate brushes
        elements.cmbPen.innerHTML = "";
        data.brushes.forEach(br => {
            const opt = document.createElement("option");
            opt.value = br;
            opt.textContent = br;
            elements.cmbPen.appendChild(opt);
        });
    } catch (e) {
        console.error("Failed to load assets lists:", e);
    }
}

async function loadVoicesList() {
    try {
        const resp = await fetch(`${API_BASE}/api/voices`);
        const data = await resp.json();
        edgeVoices = data.edge;
        capcutVoices = data.capcut;
        updateVoiceCombobox();
    } catch (e) {
        console.error("Failed to load tts voices:", e);
    }
}

function updateVoiceCombobox() {
    const model = elements.cmbTtsModel.value;
    const voices = model === "Edge-TTS" ? edgeVoices : capcutVoices;
    
    elements.cmbVoice.innerHTML = "";
    
    if (voices.length === 0) {
        const opt = document.createElement("option");
        opt.textContent = "Đang tải giọng đọc...";
        elements.cmbVoice.appendChild(opt);
        return;
    }
    
    voices.forEach(v => {
        const opt = document.createElement("option");
        opt.value = v.ShortName;
        opt.textContent = v.FriendlyName;
        elements.cmbVoice.appendChild(opt);
    });
    
    // Set default voice selections
    if (model === "Edge-TTS") {
        const defaultVoice = voices.find(v => v.ShortName.includes("HoaiMy")) || voices[0];
        elements.cmbVoice.value = defaultVoice.ShortName;
    } else {
        const defaultVoice = voices.find(v => v.FriendlyName.includes("Nhỏ Ngọt Ngào")) || voices[0];
        elements.cmbVoice.value = defaultVoice.ShortName;
    }
}

elements.cmbTtsModel.addEventListener("change", updateVoiceCombobox);

// --- EVENT LISTENERS (UI CONTROLS) ---
function setupEventListeners() {
    // Slider values synchronization
    elements.sldRate.addEventListener("input", (e) => {
        elements.lblRateVal.textContent = `${e.target.value >= 0 ? "+" : ""}${e.target.value}%`;
    });
    elements.sldPitch.addEventListener("input", (e) => {
        elements.lblPitchVal.textContent = `${e.target.value >= 0 ? "+" : ""}${e.target.value}Hz`;
    });
    elements.sldWidth.addEventListener("input", (e) => {
        elements.lblWidthVal.textContent = `${(e.target.value / 10).toFixed(1)}px`;
    });
    elements.sldMvol.addEventListener("input", (e) => {
        elements.lblMvolVal.textContent = `${e.target.value}%`;
    });
    elements.sldVvol.addEventListener("input", (e) => {
        elements.lblVvolVal.textContent = `${e.target.value}%`;
    });
    
    // Sync color preview
    elements.pickerColor.addEventListener("input", (e) => {
        elements.frameColorPrev.style.backgroundColor = e.target.value;
    });
    elements.frameColorPrev.addEventListener("click", () => {
        elements.pickerColor.click();
    });
    
    // BGM Selection
    elements.btnBrowseBgm.addEventListener("click", () => elements.bgmFileInput.click());
    elements.bgmFileInput.addEventListener("change", async (e) => {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            uploadAssetFile(file, "bgm", (data) => {
                elements.entryBgm.value = file.name;
                elements.entryBgm.dataset.serverPath = data.url;
                appendLog(`[Upload BGM] Tải lên thành công: ${file.name}`);
            });
        }
    });

    // Custom Brush & Background uploads
    elements.btnUploadBrush.addEventListener("click", () => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".png,.jpg,.jpeg";
        input.onchange = async (e) => {
            if (e.target.files.length > 0) {
                const file = e.target.files[0];
                uploadAssetFile(file, "brush", () => {
                    loadAssetsLists();
                    appendLog(`[Upload Cọ] Đã thêm cọ vẽ tùy chỉnh: ${file.name}`);
                });
            }
        };
        input.click();
    });

    elements.btnUploadBg.addEventListener("click", () => {
        const input = document.createElement("input");
        input.type = "file";
        input.accept = ".png,.jpg,.jpeg";
        input.onchange = async (e) => {
            if (e.target.files.length > 0) {
                const file = e.target.files[0];
                uploadAssetFile(file, "background", () => {
                    loadAssetsLists();
                    appendLog(`[Upload Giấy] Đã thêm nền giấy tùy chỉnh: ${file.name}`);
                });
            }
        };
        input.click();
    });

    // Mode changer
    Array.from(elements.appModeRadios).forEach(radio => {
        radio.addEventListener("change", (e) => {
            const mode = e.target.value;
            // Disable TTS voice tab if video only
            const ttsBtn = document.getElementById("tab_tts_btn");
            if (mode === "video_only") {
                ttsBtn.disabled = true;
                if (ttsBtn.classList.contains("active")) {
                    document.getElementById("tab_style_btn").click();
                }
            } else {
                ttsBtn.disabled = false;
            }
            renderScenes();
        });
    });

    // Sidebar Tabs switching
    const tabButtons = document.querySelectorAll(".tab-btn");
    tabButtons.forEach(btn => {
        btn.addEventListener("click", () => {
            if (btn.disabled) return;
            tabButtons.forEach(b => b.classList.remove("active"));
            document.querySelectorAll(".tab-pane").forEach(p => p.classList.remove("active"));
            
            btn.classList.add("active");
            document.getElementById(btn.dataset.tab).classList.add("active");
        });
    });

    // Scene add card trigger
    elements.btnAddScene.addEventListener("click", () => {
        addScene();
    });

    // Render trigger buttons
    elements.btnRender.addEventListener("click", triggerRenderStart);
    elements.btnPause.addEventListener("click", triggerRenderPause);
    elements.btnResume.addEventListener("click", triggerRenderResume);
    elements.btnCancel.addEventListener("click", triggerRenderCancel);
    
    // Log Management buttons
    elements.btnLogoUpload.addEventListener("click", () => elements.logoFileInput.click());
    elements.logoFileInput.addEventListener("change", async (e) => {
        if (e.target.files.length > 0) {
            const file = e.target.files[0];
            uploadAssetFile(file, "logo", (data) => {
                // Add logo to logs list
                const newLogo = {
                    path: data.url,
                    filename: file.name,
                    cx_pct: 0.5,
                    cy_pct: 0.5,
                    scale_pct: 0.15
                };
                logos.push(newLogo);
                updateLogoDropdown();
                appendLog(`[Upload Logo] Đã thêm logo: ${file.name}`);
            });
        }
    });

    elements.btnLogoDel.addEventListener("click", () => {
        const selectedIdx = elements.cmbLogos.selectedIndex;
        if (selectedIdx >= 0) {
            logos.splice(selectedIdx, 1);
            updateLogoDropdown();
            appendLog("[Logo] Đã xóa logo được chọn.");
        }
    });

    // Logo Position Dialog
    elements.btnLogoPos.addEventListener("click", openLogoPositionDialog);
    elements.btnCloseLogoModal.addEventListener("click", () => elements.logoModal.classList.remove("active"));
    elements.btnCancelLogoPos.addEventListener("click", () => elements.logoModal.classList.remove("active"));
    elements.btnSaveLogoPos.addEventListener("click", saveLogoPositions);
    elements.cmbActiveDialogLogo.addEventListener("change", (e) => {
        selectedLogoIndex = parseInt(e.target.value);
        updateLogoDialogPreview();
    });
    elements.logoScaleSlider.addEventListener("input", (e) => {
        const val = e.target.value;
        elements.lblLogoScaleVal.textContent = `${val}%`;
        if (logos[selectedLogoIndex]) {
            logos[selectedLogoIndex].scale_pct = val / 100;
            updateLogoDialogPreview();
        }
    });

    // Bulk upload buttons
    elements.btnUploadImages.addEventListener("click", () => elements.bulkImagesInput.click());
    elements.bulkImagesInput.addEventListener("change", handleBulkImagesUpload);
    elements.btnUploadScript.addEventListener("click", () => elements.bulkScriptInput.click());
    elements.bulkScriptInput.addEventListener("change", handleBulkScriptUpload);

    // Save/Load project actions
    elements.btnSaveProj.addEventListener("click", saveProjectToFile);
    elements.btnLoadProj.addEventListener("click", () => elements.projectFileInput.click());
    elements.projectFileInput.addEventListener("change", loadProjectFromFile);
}

// --- STORYBOARD SCENE ROW ACTIONS ---
function getAppMode() {
    return Array.from(elements.appModeRadios).find(r => r.checked).value;
}

function addScene(data = {}) {
    const newScene = {
        image_path: data.image_path || "",
        image_name: data.image_name || "",
        script: data.script || "",
        draw_time: data.draw_time !== undefined ? data.draw_time : 5.0,
        hold_time: data.hold_time !== undefined ? data.hold_time : 3.0,
        timestamp: data.timestamp || "",
        transition: data.transition || "random"
    };
    scenes.push(newScene);
    renderScenes();
}

function deleteScene(idx) {
    scenes.splice(idx, 1);
    renderScenes();
}

function renderScenes() {
    elements.storyboardContainer.innerHTML = "";
    const mode = getAppMode();
    
    if (scenes.length === 0) {
        elements.storyboardContainer.innerHTML = `<div class="empty-state">Bảng phân cảnh trống. Hãy thêm các cảnh vẽ.</div>`;
        return;
    }
    
    scenes.forEach((sc, idx) => {
        const card = document.createElement("div");
        card.className = "scene-row-card";
        if (sc.timestamp) {
            card.classList.add("has-timestamp");
        }
        card.draggable = true;
        card.dataset.index = idx;
        
        // HTML templates matching the complex desktop inputs
        let modeInputsHtml = "";
        if (mode === "video_voice") {
            modeInputsHtml = `
                <textarea class="scene-script-text" placeholder="Thuyết minh cảnh ${idx + 1}...">${sc.script}</textarea>
                ${sc.timestamp ? `
                <div class="scene-timestamp-row">
                    <span>Timestamp:</span>
                    <input type="text" value="${sc.timestamp}" readonly>
                </div>` : ""}
            `;
        } else {
            // Video-only mode spinners
            modeInputsHtml = `
                <div class="scene-time-container">
                    <div class="time-spinner-vbox">
                        <span>Thời gian vẽ (s):</span>
                        <input type="number" step="0.1" class="spin-draw" value="${sc.draw_time.toFixed(1)}">
                    </div>
                    <div class="time-spinner-vbox">
                        <span>Thời gian giữ (s):</span>
                        <input type="number" step="0.1" class="spin-hold" value="${sc.hold_time.toFixed(1)}">
                    </div>
                    ${sc.timestamp ? `
                    <div class="scene-timestamp-row">
                        <span>Timestamp:</span>
                        <input type="text" value="${sc.timestamp}" readonly>
                    </div>` : ""}
                </div>
            `;
        }
        
        card.innerHTML = `
            <div class="scene-index-handle">Cảnh #${idx + 1}</div>
            <div class="scene-thumbnail-btn" title="Chọn hình ảnh">
                ${sc.image_path ? `<img src="${API_BASE}${sc.image_path}" alt="Thumb">` : `<span>+ Chọn Ảnh</span>`}
                <div class="hover-overlay">
                    <svg viewBox="0 0 24 24" width="16" height="16"><path fill="currentColor" d="M21 19V5c0-1.1-.9-2-2-2H5c-1.1 0-2 .9-2 2v14c0 1.1.9 2 2 2h14c0-1.1.9-2 2-2ZM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5Z"/></svg>
                    <span>Thay thế</span>
                </div>
                <input type="file" class="scene-file-input" accept=".png,.jpg,.jpeg" style="display:none;">
            </div>
            
            <div class="scene-content-vbox">
                ${modeInputsHtml}
            </div>
            
            <div class="scene-transition-vbox">
                <span>Chuyển cảnh:</span>
                <select class="cmb-trans">
                    <option value="none" ${sc.transition === "none" ? "selected" : ""}>Không (Cut)</option>
                    <option value="random" ${sc.transition === "random" ? "selected" : ""}>Ngẫu nhiên</option>
                    <option value="fade" ${sc.transition === "fade" ? "selected" : ""}>Mờ dần</option>
                    <option value="wipeleft" ${sc.transition === "wipeleft" ? "selected" : ""}>Quét trái</option>
                    <option value="wiperight" ${sc.transition === "wiperight" ? "selected" : ""}>Quét phải</option>
                    <option value="slideleft" ${sc.transition === "slideleft" ? "selected" : ""}>Trượt trái</option>
                    <option value="slideright" ${sc.transition === "slideright" ? "selected" : ""}>Trượt phải</option>
                    <option value="dissolve" ${sc.transition === "dissolve" ? "selected" : ""}>Hòa tan</option>
                    <option value="zoomin" ${sc.transition === "zoomin" ? "selected" : ""}>Phóng to</option>
                </select>
            </div>
            
            <button class="btn-scene-delete" title="Xóa cảnh">&times;</button>
        `;
        
        // --- WIRE STORYBOARD ROW EVENTS ---
        const fileInput = card.querySelector(".scene-file-input");
        const thumbBtn = card.querySelector(".scene-thumbnail-btn");
        
        thumbBtn.addEventListener("click", () => fileInput.click());
        fileInput.addEventListener("change", async (e) => {
            if (e.target.files.length > 0) {
                const file = e.target.files[0];
                uploadAssetFile(file, "image", (data) => {
                    sc.image_path = data.url;
                    sc.image_name = file.name;
                    renderScenes();
                });
            }
        });
        
        // Listeners for text/time/transition changes
        const scriptArea = card.querySelector(".scene-script-text");
        if (scriptArea) {
            scriptArea.addEventListener("input", (e) => {
                sc.script = e.target.value;
            });
        }
        
        const spinDraw = card.querySelector(".spin-draw");
        if (spinDraw) {
            spinDraw.addEventListener("change", (e) => {
                sc.draw_time = parseFloat(e.target.value) || 5.0;
            });
        }
        
        const spinHold = card.querySelector(".spin-hold");
        if (spinHold) {
            spinHold.addEventListener("change", (e) => {
                sc.hold_time = parseFloat(e.target.value) || 3.0;
            });
        }
        
        const cmbTrans = card.querySelector(".cmb-trans");
        cmbTrans.addEventListener("change", (e) => {
            sc.transition = e.target.value;
        });
        
        card.querySelector(".btn-scene-delete").addEventListener("click", () => {
            deleteScene(idx);
        });
        
        // HTML5 Drag and Drop logic for reordering scenes
        card.addEventListener("dragstart", (e) => {
            card.classList.add("dragging");
            e.dataTransfer.setData("text/plain", idx);
        });
        
        card.addEventListener("dragend", () => {
            card.classList.remove("dragging");
            document.querySelectorAll(".scene-row-card").forEach(c => c.classList.remove("drag-over"));
        });
        
        card.addEventListener("dragover", (e) => {
            e.preventDefault();
            card.classList.add("drag-over");
        });
        
        card.addEventListener("dragleave", () => {
            card.classList.remove("drag-over");
        });
        
        card.addEventListener("drop", (e) => {
            e.preventDefault();
            const fromIdx = parseInt(e.dataTransfer.getData("text/plain"));
            const toIdx = idx;
            if (fromIdx !== toIdx) {
                const moved = scenes.splice(fromIdx, 1)[0];
                scenes.splice(toIdx, 0, moved);
                renderScenes();
            }
        });
        
        elements.storyboardContainer.appendChild(card);
    });
}

// --- FILE UPLOAD LOGIC ---
async function uploadAssetFile(file, type, successCb) {
    const formData = new FormData();
    formData.append("file", file);
    
    try {
        const resp = await fetch(`${API_BASE}/api/upload/${type}`, {
            method: "POST",
            body: formData
        });
        const data = await resp.json();
        if (resp.ok) {
            if (successCb) successCb(data);
        } else {
            alert(`Lỗi upload file: ${data.detail || "Không rõ nguyên nhân"}`);
        }
    } catch (e) {
        console.error("Upload request failed:", e);
        alert("Lỗi kết nối khi upload file.");
    }
}

// --- LOG MANAGEMENT DRAG-N-DROP DIALOG ---
function updateLogoDropdown() {
    elements.cmbLogos.innerHTML = "";
    if (logos.length === 0) {
        const opt = document.createElement("option");
        opt.textContent = "Không có logo nào...";
        elements.cmbLogos.appendChild(opt);
        return;
    }
    logos.forEach((l, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        opt.textContent = `${idx + 1}. ${l.filename}`;
        elements.cmbLogos.appendChild(opt);
    });
}

function openLogoPositionDialog() {
    if (logos.length === 0) {
        alert("Vui lòng tải lên ít nhất một logo trước!");
        return;
    }
    
    // Populate dropdown
    elements.cmbActiveDialogLogo.innerHTML = "";
    logos.forEach((l, idx) => {
        const opt = document.createElement("option");
        opt.value = idx;
        opt.textContent = `${idx + 1}. ${l.filename}`;
        elements.cmbActiveDialogLogo.appendChild(opt);
    });
    
    selectedLogoIndex = 0;
    elements.cmbActiveDialogLogo.value = 0;
    
    const activeLogo = logos[selectedLogoIndex];
    elements.logoScaleSlider.value = parseInt(activeLogo.scale_pct * 100);
    elements.lblLogoScaleVal.textContent = `${elements.logoScaleSlider.value}%`;
    
    elements.logoModal.classList.add("active");
    updateLogoDialogPreview();
}

function updateLogoDialogPreview() {
    const screenSim = elements.logoDragzone.querySelector(".canvas-screen-sim");
    
    // Clear all draggable elements except the label
    Array.from(screenSim.children).forEach(c => {
        if (!c.classList.contains("canvas-screen-label")) {
            screenSim.removeChild(c);
        }
    });
    
    // Renders logos as absolute elements inside simulation screen
    logos.forEach((logo, idx) => {
        const item = document.createElement("div");
        item.className = "sim-logo-draggable";
        if (idx === selectedLogoIndex) {
            item.classList.add("selected");
        }
        
        // CSS position layout based on percentages
        const wPct = logo.scale_pct * 100;
        item.style.width = `${wPct}%`;
        item.style.aspectRatio = "1 / 1"; // Square approximation
        item.style.left = `calc(${logo.cx_pct * 100}% - ${wPct / 2}%)`;
        item.style.top = `calc(${logo.cy_pct * 100}% - ${wPct / 2}%)`;
        
        item.innerHTML = `
            <img src="${API_BASE}${logo.path}" alt="logo">
            <div class="sim-logo-center-dot"></div>
        `;
        
        // Wire drag event handles manually
        item.addEventListener("mousedown", (e) => {
            e.preventDefault();
            selectedLogoIndex = idx;
            elements.cmbActiveDialogLogo.value = idx;
            elements.logoScaleSlider.value = parseInt(logo.scale_pct * 100);
            elements.lblLogoScaleVal.textContent = `${elements.logoScaleSlider.value}%`;
            
            // Mark selected
            document.querySelectorAll(".sim-logo-draggable").forEach(el => el.classList.remove("selected"));
            item.classList.add("selected");
            
            const startX = e.clientX;
            const startY = e.clientY;
            const screenRect = screenSim.getBoundingClientRect();
            const startCx = logo.cx_pct;
            const startCy = logo.cy_pct;
            
            const onMouseMove = (moveEvent) => {
                const dx = moveEvent.clientX - startX;
                const dy = moveEvent.clientY - startY;
                
                logo.cx_pct = Math.max(0, Math.min(1, startCx + (dx / screenRect.width)));
                logo.cy_pct = Math.max(0, Math.min(1, startCy + (dy / screenRect.height)));
                
                // Redraw pos
                item.style.left = `calc(${logo.cx_pct * 100}% - ${wPct / 2}%)`;
                item.style.top = `calc(${logo.cy_pct * 100}% - ${wPct / 2}%)`;
            };
            
            const onMouseUp = () => {
                document.removeEventListener("mousemove", onMouseMove);
                document.removeEventListener("mouseup", onMouseUp);
            };
            
            document.addEventListener("mousemove", onMouseMove);
            document.addEventListener("mouseup", onMouseUp);
        });
        
        screenSim.appendChild(item);
    });
}

function saveLogoPositions() {
    elements.logoModal.classList.remove("active");
    appendLog("[Logo] Cập nhật vị trí logo thành công.");
}

// --- BULK OPERATIONS ---
async function handleBulkImagesUpload(e) {
    const files = Array.from(e.target.files);
    if (files.length === 0) return;
    
    appendLog(`[Bulk Image] Bắt đầu tải lên ${files.length} ảnh...`);
    
    // Upload in series or parallel
    for (const file of files) {
        await new Promise((resolve) => {
            uploadAssetFile(file, "image", (data) => {
                addScene({
                    image_path: data.url,
                    image_name: file.name,
                    script: ""
                });
                appendLog(`[Bulk Image] Tải lên thành công: ${file.name}`);
                resolve();
            });
        });
    }
}

function parseSrtScript(content) {
    const blocks = content.trim().split(/\n\s*\n/);
    const results = [];
    for (const block of blocks) {
        const lines = block.split('\n').map(l => l.trim()).filter(l => l.length > 0);
        if (lines.length >= 3) {
            if (lines[1].includes('-->')) {
                const timestamp = lines[1];
                const text = lines.slice(2).join(' ');
                if (text) {
                    results.push({ script: text, timestamp: timestamp });
                }
            } else {
                let time_line = "";
                const text_lines = [];
                for (const line of lines) {
                    if (line.includes('-->')) {
                        time_line = line;
                    } else if (!/^\d+$/.test(line)) {
                        text_lines.push(line);
                    }
                }
                const text = text_lines.join(' ');
                if (text) {
                    results.push({ script: text, timestamp: time_line });
                }
            }
        } else if (lines.length === 2) {
            if (lines[0].includes('-->')) {
                results.push({ script: lines[1], timestamp: lines[0] });
            }
        } else if (lines.length === 1) {
            const line = lines[0];
            if (!/^\d+$/.test(line) && !line.includes('-->')) {
                results.push({ script: line, timestamp: "" });
            }
        }
    }
    return results;
}

async function handleBulkScriptUpload(e) {
    if (e.target.files.length === 0) return;
    const file = e.target.files[0];
    
    const reader = new FileReader();
    reader.onload = function(evt) {
        const text = evt.target.result;
        let results = [];
        
        if (file.name.toLowerCase().endsWith(".srt")) {
            results = parseSrtScript(text);
        } else {
            const paragraphs = text.split("\n").map(p => p.trim()).filter(p => p.length > 0);
            results = paragraphs.map(p => ({ script: p, timestamp: "" }));
        }
        
        appendLog(`[Bulk Script] Đã đọc ${results.length} đoạn văn bản từ: ${file.name}`);
        
        // Ask for merge/replace
        const confirmMerge = confirm("Bạn có muốn ghép kịch bản này vào các cảnh hiện có không?\n(Chọn 'Cancel' sẽ xóa sạch cảnh hiện tại và tạo mới)");
        if (!confirmMerge) {
            scenes = [];
        }
        
        results.forEach((item, idx) => {
            if (idx < scenes.length) {
                scenes[idx].script = item.script;
                scenes[idx].timestamp = item.timestamp;
            } else {
                addScene({
                    image_path: "",
                    script: item.script,
                    timestamp: item.timestamp
                });
            }
        });
        renderScenes();
    };
    reader.readAsText(file);
}

// --- PROJECT SAVE / LOAD ---
function saveProjectToFile() {
    const resolutionVal = elements.cmbRes.value.split(",").map(Number);
    
    const projectData = {
        version: "26.7.30",
        mode: getAppMode(),
        voice: elements.cmbVoice.value,
        tts_model: elements.cmbTtsModel.value,
        rate: parseInt(elements.sldRate.value),
        pitch: parseInt(elements.sldPitch.value),
        pen_style: elements.cmbPen.value,
        bg_style: elements.cmbBg.value,
        pen_color: elements.pickerColor.value,
        pen_width: parseFloat(elements.sldWidth.value / 10),
        color_option: elements.cmbColorOpt.value,
        draw_direction: elements.cmbDrawDirection.value,
        music_path: elements.entryBgm.dataset.serverPath || "",
        music_name: elements.entryBgm.value || "",
        voice_volume: parseFloat(elements.sldVvol.value / 100),
        music_volume: parseFloat(elements.sldMvol.value / 100),
        color_style: elements.cmbColorStyle.value,
        camera_enabled: elements.swCamera.checked,
        spatial_grouping: elements.swSmartOrder.checked,
        slide_transition: elements.swSlideTransition.checked,
        resolution: resolutionVal,
        fps: parseInt(elements.cmbFps.value),
        export_mode: elements.cmbExportMode.value,
        logos: logos,
        scenes: scenes
    };
    
    const jsonStr = JSON.stringify(projectData, null, 4);
    const blob = new Blob([jsonStr], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    
    const a = document.createElement("a");
    a.href = url;
    a.download = `project_${new Date().toISOString().slice(0,10)}.json`;
    a.click();
    
    URL.revokeObjectURL(url);
    appendLog("[Project] Lưu tệp cấu hình dự án thành công.");
}

function loadProjectFromFile(e) {
    if (e.target.files.length === 0) return;
    const file = e.target.files[0];
    
    const reader = new FileReader();
    reader.onload = function(evt) {
        try {
            const data = JSON.parse(evt.target.result);
            
            // Sync settings inputs
            if (data.mode) {
                Array.from(elements.appModeRadios).forEach(r => {
                    r.checked = (r.value === data.mode);
                });
            }
            
            if (data.tts_model) elements.cmbTtsModel.value = data.tts_model;
            updateVoiceCombobox();
            if (data.voice) elements.cmbVoice.value = data.voice;
            
            if (data.rate !== undefined) {
                elements.sldRate.value = data.rate;
                elements.lblRateVal.textContent = `${data.rate >= 0 ? "+" : ""}${data.rate}%`;
            }
            if (data.pitch !== undefined) {
                elements.sldPitch.value = data.pitch;
                elements.lblPitchVal.textContent = `${data.pitch >= 0 ? "+" : ""}${data.pitch}Hz`;
            }
            if (data.pen_style) elements.cmbPen.value = data.pen_style;
            if (data.bg_style) elements.cmbBg.value = data.bg_style;
            if (data.pen_color) {
                elements.pickerColor.value = data.pen_color;
                elements.frameColorPrev.style.backgroundColor = data.pen_color;
            }
            if (data.pen_width !== undefined) {
                elements.sldWidth.value = data.pen_width * 10;
                elements.lblWidthVal.textContent = `${data.pen_width.toFixed(1)}px`;
            }
            if (data.color_option) elements.cmbColorOpt.value = data.color_option;
            if (data.draw_direction) elements.cmbDrawDirection.value = data.draw_direction;
            if (data.music_name) {
                elements.entryBgm.value = data.music_name;
                elements.entryBgm.dataset.serverPath = data.music_path;
            }
            if (data.music_volume !== undefined) {
                elements.sldMvol.value = data.music_volume * 100;
                elements.lblMvolVal.textContent = `${elements.sldMvol.value}%`;
            }
            if (data.voice_volume !== undefined) {
                elements.sldVvol.value = data.voice_volume * 100;
                elements.lblVvolVal.textContent = `${elements.sldVvol.value}%`;
            }
            if (data.color_style) elements.cmbColorStyle.value = data.color_style;
            if (data.camera_enabled !== undefined) elements.swCamera.checked = data.camera_enabled;
            if (data.spatial_grouping !== undefined) elements.swSmartOrder.checked = data.spatial_grouping;
            if (data.slide_transition !== undefined) elements.swSlideTransition.checked = data.slide_transition;
            if (data.resolution) elements.cmbRes.value = data.resolution.join(",");
            if (data.fps) elements.cmbFps.value = data.fps;
            if (data.export_mode) elements.cmbExportMode.value = data.export_mode;
            
            if (data.logos) {
                logos = data.logos;
                updateLogoDropdown();
            }
            if (data.scenes) {
                scenes = data.scenes;
                renderScenes();
            }
            
            appendLog(`[Project] Tải thành công dự án: ${file.name}`);
        } catch (err) {
            console.error("Load project error:", err);
            alert("Tệp dự án không hợp lệ.");
        }
    };
    reader.readAsText(file);
}

// --- REAL-TIME VIDEO RENDERING & WS MONITOR ---
async function triggerRenderStart() {
    // 1. Validations
    if (scenes.length === 0) {
        alert(TRANSLATIONS[currentLanguage].alert_no_scenes);
        return;
    }
    
    const missingImage = scenes.some(sc => !sc.image_path);
    if (missingImage) {
        alert(TRANSLATIONS[currentLanguage].alert_missing_image);
        return;
    }
    
    // Lock controls
    lockRenderControls(true);
    
    // Clear logs console
    elements.txtLogs.textContent = "";
    appendLog("[System] Chuẩn bị gửi yêu cầu render...");
    
    // 2. Prep generation payload
    const hexToRgb = (hex) => {
        const bigint = parseInt(hex.slice(1), 16);
        return [(bigint >> 16) & 255, (bigint >> 8) & 255, bigint & 255];
    };
    
    const resolutionVal = elements.cmbRes.value.split(",").map(Number);
    const payload = {
        settings: {
            mode: getAppMode(),
            voice: elements.cmbVoice.value,
            tts_model: elements.cmbTtsModel.value,
            rate: parseInt(elements.sldRate.value),
            pitch: parseInt(elements.sldPitch.value),
            pen_style: elements.cmbPen.value,
            bg_style: elements.cmbBg.value,
            pen_color: hexToRgb(elements.pickerColor.value),
            pen_width: parseFloat(elements.sldWidth.value / 10),
            color_option: elements.cmbColorOpt.value,
            draw_direction: elements.cmbDrawDirection.value,
            music_path: elements.entryBgm.dataset.serverPath || "",
            voice_volume: parseFloat(elements.sldVvol.value / 100),
            music_volume: parseFloat(elements.sldMvol.value / 100),
            color_style: elements.cmbColorStyle.value,
            camera_enabled: elements.swCamera.checked,
            spatial_grouping: elements.swSmartOrder.checked,
            slide_transition: elements.swSlideTransition.checked,
            resolution: resolutionVal,
            fps: parseInt(elements.cmbFps.value),
            export_mode: elements.cmbExportMode.value,
            logos: logos,
            scenes: scenes
        }
    };
    
    try {
        const resp = await fetch(`${API_BASE}/api/render/start`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify(payload)
        });
        
        if (resp.status === 403) {
            alert("Bản quyền chưa kích hoạt. Vui lòng kích hoạt bản quyền trước!");
            lockRenderControls(false);
            return;
        }
        
        const data = await resp.json();
        if (data.success) {
            activeJobId = data.job_id;
            appendLog(`[System] Job Render khởi động thành công (ID: ${activeJobId})`);
            connectWebSocket(activeJobId);
        } else {
            alert(`Lỗi khởi tạo render: ${data.detail || "Không rõ nguyên nhân"}`);
            lockRenderControls(false);
        }
    } catch (e) {
        console.error("Render start API failed:", e);
        alert("Lỗi kết nối tới backend API.");
        lockRenderControls(false);
    }
}

function connectWebSocket(jobId) {
    if (wsConn) {
        wsConn.close();
    }
    
    const token = localStorage.getItem("dkc_auth_token");
    const wsUrl = `${WS_BASE}/ws/render?job_id=${jobId}${token ? `&token=${token}` : ""}`;
    wsConn = new WebSocket(wsUrl);
    
    wsConn.onopen = () => {
        appendLog("[WebSocket] Kết nối dòng giám sát thành công.");
    };
    
    wsConn.onmessage = (e) => {
        const data = JSON.parse(e.data);
        if (data.error) {
            appendLog(`[WebSocket Error] ${data.error}`);
            wsConn.close();
            return;
        }
        
        // 1. Update status
        elements.lblProgress.textContent = data.status_text;
        
        // 2. Update ETA
        const minutes = Math.floor(data.eta_seconds / 60);
        const seconds = data.eta_seconds % 60;
        elements.lblEta.textContent = `ETA: ${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
        
        // 3. Progress bar width
        const pct = (data.progress * 100).toFixed(1);
        elements.progressBarChunk.style.width = `${pct}%`;
        
        // 4. Draw canvas preview frames in real-time
        if (data.preview_frame) {
            drawPreviewFrame(data.preview_frame);
        }
        
        // 5. Stream system logs
        if (data.new_logs && data.new_logs.length > 0) {
            data.new_logs.forEach(log => appendLog(log));
        }
        
        // 6. Handle finished states
        if (data.status === "success") {
            appendLog(`[System] Render hoàn tất thành công!`);
            alert(TRANSLATIONS[currentLanguage].render_success);
            
            // Show download link
            if (data.download_url) {
                appendLog(`[System] Video của bạn đã sẵn sàng tải về:`);
                appendLog(`[LINK DOWNLOAD] ${API_BASE}${data.download_url}`);
                
                // Autotrigger download
                const a = document.createElement("a");
                a.href = `${API_BASE}${data.download_url}`;
                a.download = `drawing_video_${Date.now()}.mp4`;
                a.click();
            }
            
            finalizeRenderJob(true);
        } else if (data.status === "failed") {
            appendLog(`[System] Render bị lỗi: ${data.status_text}`);
            alert(`${TRANSLATIONS[currentLanguage].render_failed}: ${data.status_text}`);
            finalizeRenderJob(false);
        } else if (data.status === "cancelled") {
            appendLog(`[System] Đã hủy render.`);
            finalizeRenderJob(false);
        }
    };
    
    wsConn.onclose = () => {
        appendLog("[WebSocket] Ngắt kết nối giám sát.");
    };
}

function drawPreviewFrame(base64Data) {
    const img = new Image();
    img.onload = function() {
        canvasCtx.clearRect(0, 0, elements.previewCanvas.width, elements.previewCanvas.height);
        canvasCtx.drawImage(img, 0, 0, elements.previewCanvas.width, elements.previewCanvas.height);
    };
    img.src = `data:image/jpeg;base64,${base64Data}`;
}

async function triggerRenderPause() {
    if (!activeJobId) return;
    try {
        const resp = await fetch(`${API_BASE}/api/render/pause/${activeJobId}`, { method: "POST" });
        if (resp.ok) {
            elements.btnPause.disabled = true;
            elements.btnResume.disabled = false;
            elements.lblProgress.textContent = "Tạm dừng tiến trình...";
            appendLog("[System] Tạm dừng render.");
        }
    } catch (e) {
        console.error(e);
    }
}

async function triggerRenderResume() {
    if (!activeJobId) return;
    try {
        const resp = await fetch(`${API_BASE}/api/render/resume/${activeJobId}`, { method: "POST" });
        if (resp.ok) {
            elements.btnPause.disabled = false;
            elements.btnResume.disabled = true;
            elements.lblProgress.textContent = "Đang tiếp tục...";
            appendLog("[System] Tiếp tục render.");
        }
    } catch (e) {
        console.error(e);
    }
}

async function triggerRenderCancel() {
    if (!activeJobId) return;
    if (confirm(TRANSLATIONS[currentLanguage].confirm_cancel)) {
        try {
            await fetch(`${API_BASE}/api/render/cancel/${activeJobId}`, { method: "POST" });
            appendLog("[System] Yêu cầu hủy bỏ tiến trình...");
        } catch (e) {
            console.error(e);
        }
    }
}

function finalizeRenderJob(success) {
    lockRenderControls(false);
    activeJobId = null;
    if (wsConn) {
        wsConn.close();
        wsConn = null;
    }
}

function lockRenderControls(lock) {
    elements.btnRender.disabled = lock;
    elements.btnCancel.disabled = !lock;
    elements.btnPause.disabled = !lock;
    elements.btnResume.disabled = true; // Always disabled initially on lock
    
    // Disable timeline edit inputs
    document.querySelectorAll(".scene-script-text, .spin-draw, .spin-hold, .cmb-trans, .btn-scene-delete, .scene-thumbnail-btn, #btn-add-scene, #btn_upload_images, #btn_upload_script, #btn_load_proj").forEach(el => {
        el.disabled = lock;
        if (lock) el.style.pointerEvents = "none";
        else el.style.pointerEvents = "auto";
    });
}

// --- UTILITY LOGGER FUNCTIONS ---
function appendLog(line) {
    const cleanLine = line.replace(/\r/g, "");
    elements.txtLogs.textContent += cleanLine + "\n";
    elements.txtLogs.scrollTop = elements.txtLogs.scrollHeight;
}
