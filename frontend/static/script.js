// DOM элементы
const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileInfo = document.getElementById('fileInfo');
const uploadBtn = document.getElementById('uploadBtn');
const progressCard = document.getElementById('progressCard');
const taskIdSpan = document.getElementById('taskId');
const progressFill = document.getElementById('progressFill');
const progressStatus = document.getElementById('progressStatus');
const downloadBtn = document.getElementById('downloadBtn');
const resetBtn = document.getElementById('resetBtn');
const errorMessageDiv = document.getElementById('errorMessage');
const errorTextSpan = document.getElementById('errorText');

let selectedFile = null;
let currentTaskId = null;
let pollingInterval = null;

// API endpoints (относительно текущего origin, nginx проксирует)
const API_UPLOAD = '/api/upload';
const getStatusUrl = (taskId) => `/api/status/${taskId}`;
const getDownloadUrl = (taskId) => `/api/download/${taskId}`;

// Показ ошибки
function showError(message) {
    errorTextSpan.innerText = message;
    errorMessageDiv.classList.remove('hidden');
    setTimeout(() => {
        errorMessageDiv.classList.add('hidden');
    }, 6000);
}

// Скрыть ошибку
function hideError() {
    errorMessageDiv.classList.add('hidden');
}

// Сброс состояния формы
function resetUploadUI() {
    selectedFile = null;
    fileInput.value = '';
    fileInfo.innerText = '';
    uploadBtn.disabled = true;
    if (dropZone) dropZone.classList.remove('dragover');
    hideError();
}

// Обработка выбора файла
function handleFile(file) {
    if (!file) return;
    
    // Проверка размера (500 MB)
    const maxSize = 500 * 1024 * 1024;
    if (file.size > maxSize) {
        showError(`Файл слишком большой. Максимум 500 МБ. Выбранный файл: ${(file.size / (1024*1024)).toFixed(2)} МБ`);
        resetUploadUI();
        return;
    }
    
    // Допустимые типы
    const allowedTypes = ['video/mp4', 'video/quicktime', 'video/x-msvideo'];
    if (!allowedTypes.includes(file.type) && !file.name.match(/\.(mp4|mov|avi)$/i)) {
        showError('Пожалуйста, выберите видеофайл (MP4, MOV, AVI)');
        resetUploadUI();
        return;
    }
    
    selectedFile = file;
    const sizeMB = (file.size / (1024 * 1024)).toFixed(2);
    fileInfo.innerText = `📎 ${file.name} (${sizeMB} МБ)`;
    uploadBtn.disabled = false;
    hideError();
}

// Загрузка видео на сервер
async function uploadVideo() {
    if (!selectedFile) return;
    
    const formData = new FormData();
    formData.append('file', selectedFile);
    
    uploadBtn.disabled = true;
    uploadBtn.innerText = '⏳ Загрузка...';
    
    try {
        const response = await fetch(API_UPLOAD, {
            method: 'POST',
            body: formData
        });
        
        if (!response.ok) {
            let errorMsg = `Ошибка сервера: ${response.status}`;
            try {
                const errData = await response.json();
                errorMsg = errData.detail || errorMsg;
            } catch(e) {}
            throw new Error(errorMsg);
        }
        
        const data = await response.json();
        currentTaskId = data.task_id;
        
        // Показать карточку прогресса, скрыть зону загрузки
        document.querySelector('.upload-card').classList.add('hidden');
        progressCard.classList.remove('hidden');
        taskIdSpan.innerText = currentTaskId;
        progressFill.style.width = '0%';
        progressStatus.innerText = 'Задача поставлена в очередь...';
        
        // Начинаем опрос статуса
        startPolling();
        
    } catch (err) {
        showError(err.message || 'Не удалось загрузить видео');
        uploadBtn.disabled = false;
        uploadBtn.innerText = 'Загрузить видео';
        resetUploadUI();
    }
}

// Опрос статуса задачи
function startPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    
    pollingInterval = setInterval(async () => {
        if (!currentTaskId) return;
        
        try {
            const resp = await fetch(getStatusUrl(currentTaskId));
            if (!resp.ok) {
                if (resp.status === 404) {
                    stopPolling();
                    progressStatus.innerText = 'Задача не найдена';
                }
                return;
            }
            
            const data = await resp.json();
            const state = data.state;
            let progress = data.progress || 0;
            
            // progress от 0 до 10 от бэкенда → масштабируем в проценты
            let percent = Math.min(100, Math.floor((progress / 100) * 100));
            if (state === 'PROCESSING') {
                progressFill.style.width = `${percent}%`;
                progressStatus.innerText = `Обработка видео... ${percent}% (шаг ${progress}/100)`;
            } else if (state === 'PENDING') {
                progressFill.style.width = '0%';
                progressStatus.innerText = 'Ожидание начала обработки...';
            } else if (state === 'SUCCESS') {
                // Задача завершена
                stopPolling();
                progressFill.style.width = '100%';
                progressStatus.innerText = '✅ Распознавание завершено! Файл готов к скачиванию.';
                downloadBtn.classList.remove('hidden');
            } else if (state === 'FAILURE') {
                stopPolling();
                progressStatus.innerText = `❌ Ошибка: ${data.result || 'неизвестная ошибка'}`;
                showError('Обработка видео не удалась. Попробуйте другой файл.');
            }
        } catch (err) {
            console.warn('Polling error', err);
        }
    }, 2000); // опрос каждые 2 секунды
}

function stopPolling() {
    if (pollingInterval) {
        clearInterval(pollingInterval);
        pollingInterval = null;
    }
}

// Скачивание CSV
async function downloadCSV() {
    if (!currentTaskId) return;
    const downloadUrl = getDownloadUrl(currentTaskId);
    
    try {
        // Проверим сначала, что файл существует через fetch
        const response = await fetch(downloadUrl, { method: 'GET' });
        if (!response.ok) throw new Error('Файл ещё не готов');
        
        // Создаём временную ссылку и эмулируем скачивание
        const a = document.createElement('a');
        a.href = downloadUrl;
        a.download = `prices_${currentTaskId}.csv`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
    } catch (err) {
        showError('Не удалось скачать CSV. Попробуйте позже.');
    }
}

// Сброс и загрузка нового видео
function resetAndNew() {
    stopPolling();
    resetUploadUI();
    selectedFile = null;
    currentTaskId = null;
    progressCard.classList.add('hidden');
    document.querySelector('.upload-card').classList.remove('hidden');
    downloadBtn.classList.add('hidden');
    uploadBtn.innerText = 'Загрузить видео';
    uploadBtn.disabled = true;
    fileInfo.innerText = '';
    if (fileInput) fileInput.value = '';
}

// --- Drag and Drop ---
dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (e) => {
    if (e.target.files && e.target.files[0]) {
        handleFile(e.target.files[0]);
    }
});

dropZone.addEventListener('dragover', (e) => {
    e.preventDefault();
    dropZone.classList.add('dragover');
});
dropZone.addEventListener('dragleave', () => {
    dropZone.classList.remove('dragover');
});
dropZone.addEventListener('drop', (e) => {
    e.preventDefault();
    dropZone.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        handleFile(files[0]);
    }
});

uploadBtn.addEventListener('click', uploadVideo);
downloadBtn.addEventListener('click', downloadCSV);
resetBtn.addEventListener('click', resetAndNew);

// Инициализация – скрыть прогресс
progressCard.classList.add('hidden');