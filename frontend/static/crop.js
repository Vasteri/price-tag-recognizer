const FIELD_LABELS = {
    product_name: 'Название товара',
    price_default: 'Обычная цена',
    price_card: 'Цена по карте',
    price_discount: 'Цена со скидкой',
    barcode: 'Штрихкод',
    discount_amount: 'Размер скидки',
    id_sku: 'SKU',
    print_datetime: 'Дата печати',
    code: 'Код',
    additional_info: 'Дополнительная информация',
    color: 'Цвет ценника',
    special_symbols: 'Спецсимволы'
};

const dropZone = document.getElementById('dropZone');
const fileInput = document.getElementById('fileInput');
const fileInfo = document.getElementById('fileInfo');
const uploadBtn = document.getElementById('uploadBtn');
const uploadCard = document.getElementById('uploadCard');
const progressCard = document.getElementById('progressCard');
const taskIdElement = document.getElementById('taskId');
const progressFill = document.getElementById('progressFill');
const progressStatus = document.getElementById('progressStatus');
const resultSection = document.getElementById('resultSection');
const cropPreview = document.getElementById('cropPreview');
const recognitionFields = document.getElementById('recognitionFields');
const qrResult = document.getElementById('qrResult');
const qrOverlay = document.getElementById('qrOverlay');
const retryBtn = document.getElementById('retryBtn');
const resetBtn = document.getElementById('resetBtn');
const errorMessage = document.getElementById('errorMessage');
const errorText = document.getElementById('errorText');

let selectedFile = null;
let currentTaskId = null;
let pollingInterval = null;
let previewUrl = null;
let requestController = null;
let statusFailures = 0;
let selectionVersion = 0;

function showError(message) {
    errorText.textContent = message;
    errorMessage.classList.remove('hidden');
}

function hideError() {
    errorMessage.classList.add('hidden');
}

async function setFile(file) {
    const version = ++selectionVersion;
    selectedFile = null;
    uploadBtn.disabled = true;
    fileInfo.textContent = '';
    cropPreview.removeAttribute('src');
    qrOverlay.replaceChildren();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    hideError();
    if (!['image/jpeg', 'image/png', 'image/webp'].includes(file.type)) {
        showError('Поддерживаются только JPEG, PNG и WebP.');
        return;
    }
    if (!file.size || file.size > 20 * 1024 * 1024) {
        showError(file.size ? 'Изображение превышает 20 МБ.' : 'Выбран пустой файл.');
        return;
    }
    const url = URL.createObjectURL(file);
    const image = new Image();
    image.src = url;
    try {
        await image.decode();
        if (version !== selectionVersion) { URL.revokeObjectURL(url); return; }
        previewUrl = url;
        cropPreview.src = url;
        selectedFile = file;
        fileInfo.textContent = `${file.name} · ${(file.size / 1024 / 1024).toFixed(2)} МБ · ${image.naturalWidth} × ${image.naturalHeight}`;
        uploadBtn.disabled = false;
    } catch {
        URL.revokeObjectURL(url);
        if (version === selectionVersion) showError('Не удалось открыть изображение. Выберите другой файл.');
    }
}

async function uploadCrop() {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append('file', selectedFile);
    uploadBtn.disabled = true;
    uploadBtn.textContent = '⏳ Загрузка...';
    hideError();

    try {
        requestController = new AbortController();
        const response = await fetch('/api/crop/upload', { method: 'POST', body: formData, signal: requestController.signal });
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.detail || `Ошибка сервера: ${response.status}`);

        if (typeof body.task_id !== 'string' || !body.task_id) throw new Error('Сервер не вернул ID задачи.');
        currentTaskId = body.task_id;
        taskIdElement.textContent = currentTaskId;
        uploadCard.classList.add('hidden');
        progressCard.classList.remove('hidden');
        resultSection.classList.remove('hidden');
        progressFill.style.width = '0%';
        progressStatus.textContent = 'Задача поставлена в очередь...';
        startPolling();
    } catch (error) {
        if (error.name === 'AbortError') return;
        showError(error.message || 'Не удалось загрузить изображение.');
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Распознать ценник';
    }
}

async function pollStatus() {
    const taskId = currentTaskId;
    if (!taskId) return;
    const controller = new AbortController();
    requestController = controller;
    const timeout = setTimeout(() => controller.abort(), 15000);
    try {
        const response = await fetch(`/api/status/${encodeURIComponent(taskId)}`, { signal: controller.signal });
        if (!response.ok) throw new Error(`Не удалось получить статус: ${response.status}`);
        const data = await response.json();
        if (taskId !== currentTaskId) return;
        statusFailures = 0;
        hideError();
        if (data.state === 'SUCCESS') {
            progressFill.style.width = '100%';
            progressStatus.textContent = 'Распознавание завершено';
            renderResult(data.result || {});
            return;
        }
        if (['FAILURE', 'REVOKED'].includes(data.state)) {
            progressStatus.textContent = 'Не удалось распознать изображение';
            showError(typeof data.result === 'string' ? data.result : 'Ошибка обработки изображения.');
            return;
        }
        const progress = Number(data.progress);
        progressFill.style.width = `${Number.isFinite(progress) ? Math.max(0, Math.min(100, progress)) : 0}%`;
        progressStatus.textContent = data.state === 'PROCESSING'
            ? 'Изображение обрабатывается…' : 'Ожидание обработки…';
    } catch (error) {
        if (taskId !== currentTaskId) return;
        statusFailures += 1;
        if (statusFailures >= 3) {
            progressStatus.textContent = 'Связь с сервером прервана';
            showError('Не удалось получить результат. Можно повторить проверку статуса без новой загрузки.');
            retryBtn.classList.remove('hidden');
            return;
        }
        progressStatus.textContent = 'Восстанавливаем связь с сервером…';
    } finally {
        clearTimeout(timeout);
    }
    if (taskId === currentTaskId) pollingInterval = setTimeout(pollStatus, 1500);
}

function startPolling() {
    stopPolling();
    statusFailures = 0;
    retryBtn.classList.add('hidden');
    pollStatus();
}

function stopPolling() {
    clearTimeout(pollingInterval);
    pollingInterval = null;
    if (requestController) requestController.abort();
    requestController = null;
}

function renderResult(result) {
    const recognition = result.recognition || {};
    recognitionFields.replaceChildren();

    Object.entries(FIELD_LABELS).forEach(([field, label]) => {
        const labelElement = document.createElement('dt');
        const valueElement = document.createElement('dd');
        const value = recognition[field];

        labelElement.className = 'field-label';
        labelElement.textContent = label;
        valueElement.className = `field-value${value === null || value === undefined || value === '' ? ' empty' : ''}`;
        valueElement.textContent = value === null || value === undefined || value === '' ? '—' : String(value);

        recognitionFields.append(labelElement, valueElement);
    });

    qrOverlay.replaceChildren();
    qrResult.replaceChildren();
    const qrCodes = Array.isArray(result.qr_codes) ? result.qr_codes : null;
    if (qrCodes === null) {
        qrResult.textContent = 'Результат QR-детекции не предоставлен.';
        return;
    }
    if (!qrCodes.length) { qrResult.textContent = 'QR-коды не найдены.'; return; }
    qrOverlay.setAttribute('viewBox', `0 0 ${cropPreview.naturalWidth} ${cropPreview.naturalHeight}`);
    qrCodes.forEach((item, index) => {
        if (!item || typeof item !== 'object') return;
        const entry = document.createElement('div');
        entry.className = 'qr-item';
        const confidence = typeof item.confidence === 'number' && Number.isFinite(item.confidence)
            ? ` · уверенность ${(item.confidence * 100).toFixed(1)}%` : '';
        entry.textContent = `QR ${index + 1}${confidence}\n${item.data || 'Содержимое не декодировано'}`;
        qrResult.append(entry);
        const box = item.bbox;
        if (!Array.isArray(box) || box.length !== 4 || !box.every(Number.isFinite)) return;
        const [x1, y1, x2, y2] = box;
        if (x2 <= x1 || y2 <= y1) return;
        const rect = document.createElementNS('http://www.w3.org/2000/svg', 'rect');
        Object.entries({x: x1, y: y1, width: x2 - x1, height: y2 - y1,
            fill: 'none', stroke: '#16a34a', 'stroke-width': 3, 'vector-effect': 'non-scaling-stroke'})
            .forEach(([key, value]) => rect.setAttribute(key, value));
        qrOverlay.append(rect);
    });
}

function resetPage() {
    currentTaskId = null;
    selectionVersion += 1;
    stopPolling();
    retryBtn.classList.add('hidden');
    qrOverlay.replaceChildren();
    qrResult.replaceChildren();
    selectedFile = null;
    currentTaskId = null;
    fileInput.value = '';
    fileInfo.textContent = '';
    uploadBtn.disabled = true;
    uploadBtn.textContent = 'Распознать ценник';
    uploadCard.classList.remove('hidden');
    progressCard.classList.add('hidden');
    resultSection.classList.add('hidden');
    recognitionFields.replaceChildren();
    hideError();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = null;
    cropPreview.removeAttribute('src');
}

dropZone.addEventListener('click', () => fileInput.click());
fileInput.addEventListener('change', (event) => {
    if (event.target.files[0]) setFile(event.target.files[0]);
});
dropZone.addEventListener('dragover', (event) => {
    event.preventDefault();
    dropZone.classList.add('dragover');
});
dropZone.addEventListener('dragleave', () => dropZone.classList.remove('dragover'));
dropZone.addEventListener('drop', (event) => {
    event.preventDefault();
    dropZone.classList.remove('dragover');
    if (event.dataTransfer.files[0]) setFile(event.dataTransfer.files[0]);
});
uploadBtn.addEventListener('click', uploadCrop);
resetBtn.addEventListener('click', resetPage);

retryBtn.addEventListener('click', startPolling);
dropZone.addEventListener('keydown', (event) => {
    if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); fileInput.click(); }
});
window.addEventListener('pagehide', () => {
    currentTaskId = null;
    stopPolling();
    if (previewUrl) URL.revokeObjectURL(previewUrl);
});
