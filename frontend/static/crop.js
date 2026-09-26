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
const resetBtn = document.getElementById('resetBtn');
const errorMessage = document.getElementById('errorMessage');
const errorText = document.getElementById('errorText');

let selectedFile = null;
let currentTaskId = null;
let pollingInterval = null;
let previewUrl = null;

function showError(message) {
    errorText.textContent = message;
    errorMessage.classList.remove('hidden');
}

function hideError() {
    errorMessage.classList.add('hidden');
}

function setFile(file) {
    const allowedTypes = ['image/jpeg', 'image/png', 'image/webp'];
    const maxSize = 20 * 1024 * 1024;

    if (!allowedTypes.includes(file.type)) {
        selectedFile = null;
        uploadBtn.disabled = true;
        fileInfo.textContent = '';
        showError('Поддерживаются только JPEG, PNG и WebP.');
        return;
    }
    if (file.size > maxSize) {
        selectedFile = null;
        uploadBtn.disabled = true;
        fileInfo.textContent = '';
        showError('Изображение превышает максимальный размер 20 МБ.');
        return;
    }
    if (file.size === 0) {
        selectedFile = null;
        uploadBtn.disabled = true;
        fileInfo.textContent = '';
        showError('Выбран пустой файл.');
        return;
    }

    selectedFile = file;
    fileInfo.textContent = `📎 ${file.name} (${(file.size / 1024 / 1024).toFixed(2)} МБ)`;
    uploadBtn.disabled = false;
    hideError();

    if (previewUrl) URL.revokeObjectURL(previewUrl);
    previewUrl = URL.createObjectURL(file);
    cropPreview.src = previewUrl;
}

async function uploadCrop() {
    if (!selectedFile) return;

    const formData = new FormData();
    formData.append('file', selectedFile);
    uploadBtn.disabled = true;
    uploadBtn.textContent = '⏳ Загрузка...';
    hideError();

    try {
        const response = await fetch('/api/crop/upload', { method: 'POST', body: formData });
        const body = await response.json().catch(() => ({}));
        if (!response.ok) throw new Error(body.detail || `Ошибка сервера: ${response.status}`);

        currentTaskId = body.task_id;
        taskIdElement.textContent = currentTaskId;
        uploadCard.classList.add('hidden');
        progressCard.classList.remove('hidden');
        resultSection.classList.remove('hidden');
        progressFill.style.width = '0%';
        progressStatus.textContent = 'Задача поставлена в очередь...';
        startPolling();
    } catch (error) {
        showError(error.message || 'Не удалось загрузить изображение.');
        uploadBtn.disabled = false;
        uploadBtn.textContent = 'Распознать ценник';
    }
}

async function pollStatus() {
    if (!currentTaskId) return;

    try {
        const response = await fetch(`/api/status/${currentTaskId}`);
        if (!response.ok) throw new Error(`Не удалось получить статус: ${response.status}`);
        const data = await response.json();

        if (data.state === 'SUCCESS') {
            stopPolling();
            progressFill.style.width = '100%';
            progressStatus.textContent = '✅ Распознавание завершено';
            renderResult(data.result || {});
            return;
        }
        if (data.state === 'FAILURE') {
            stopPolling();
            progressStatus.textContent = '❌ Не удалось распознать изображение';
            showError(data.result || 'Ошибка обработки изображения.');
            return;
        }

        const progress = data.state === 'PROCESSING' ? Number(data.progress || 0) : 0;
        progressFill.style.width = `${Math.min(100, progress)}%`;
        progressStatus.textContent = data.state === 'PROCESSING'
            ? `VLM обрабатывает изображение... ${Math.floor(progress)}%`
            : 'Ожидание свободного worker...';
    } catch (error) {
        console.warn('Polling error', error);
    }
}

function startPolling() {
    stopPolling();
    pollStatus();
    pollingInterval = setInterval(pollStatus, 1500);
}

function stopPolling() {
    if (pollingInterval) clearInterval(pollingInterval);
    pollingInterval = null;
}

function renderResult(result) {
    const recognition = result.recognition || {};
    recognitionFields.replaceChildren();

    Object.entries(FIELD_LABELS).forEach(([field, label]) => {
        const labelElement = document.createElement('div');
        const valueElement = document.createElement('div');
        const value = recognition[field];

        labelElement.className = 'field-label';
        labelElement.textContent = label;
        valueElement.className = `field-value${value === null || value === undefined || value === '' ? ' empty' : ''}`;
        valueElement.textContent = value === null || value === undefined || value === '' ? '—' : String(value);

        recognitionFields.append(labelElement, valueElement);
    });

    const qrCodes = result.qr_codes || [];
    qrResult.textContent = qrCodes.length
        ? qrCodes.map((item) => item.data || 'QR без расшифровки').join('\n')
        : 'QR-коды не обрабатываются в текущей версии.';
}

function resetPage() {
    stopPolling();
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
