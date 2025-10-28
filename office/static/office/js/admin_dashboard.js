let currentVarietyId = null;

// System Settings Modal Functions
function openSystemSettingsModal() {
    document.getElementById('systemSettingsModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeSystemSettingsModal() {
    document.getElementById('systemSettingsModal').classList.remove('active');
    document.body.style.overflow = 'auto';
}

// Wholesale Price Modal Functions
function openWholesalePriceModal() {
    closeSystemSettingsModal();
    document.getElementById('wholesalePriceModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeWholesalePriceModal() {
    document.getElementById('wholesalePriceModal').classList.remove('active');
    document.body.style.overflow = 'auto';
    document.getElementById('wholesalePriceForm').reset();
    clearErrors();
    hideSuccessMessage('wholesalePriceSuccessMessage');
}

function openVarietyModal() {
    document.getElementById('varietyModal').classList.add('active');
    document.body.style.overflow = 'hidden';
}

function closeVarietyModal() {
    document.getElementById('varietyModal').classList.remove('active');
    document.body.style.overflow = 'auto';
    document.getElementById('varietyForm').reset();
    clearErrors();
    hideSuccessMessage('varietySuccessMessage');
}

function openProductModal(varietyData) {
    document.getElementById('product_variety').value = varietyData.sku_prefix;
    document.getElementById('productModal').classList.add('active');
    currentVarietyId = varietyData.sku_prefix;
}

function closeProductModal() {
    document.getElementById('productModal').classList.remove('active');
    document.getElementById('productForm').reset();
    const skuSuffixSelect = document.getElementById('sku_suffix');
    const defaultOption = skuSuffixSelect.querySelector('option[value="pkt"]');
    if (defaultOption) {
        defaultOption.selected = true;
    }
    clearErrors();
    hideSuccessMessage('productSuccessMessage');
}

function clearErrors() {
    const errorElements = document.querySelectorAll('.error-message');
    errorElements.forEach(element => {
        element.style.display = 'none';
        element.textContent = '';
    });
}

function showError(fieldName, message) {
    const errorElement = document.getElementById(fieldName + '_error');
    if (errorElement) {
        errorElement.textContent = message;
        errorElement.style.display = 'block';
    }
}

function showSuccessMessage(elementId) {
    const successElement = document.getElementById(elementId);
    if (successElement) {
        successElement.style.display = 'block';
        setTimeout(() => {
            successElement.style.display = 'none';
        }, 3000);
    }
}

function hideSuccessMessage(elementId) {
    const successElement = document.getElementById(elementId);
    if (successElement) {
        successElement.style.display = 'none';
    }
}

function getCookie(name) {
    let cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        const cookies = document.cookie.split(';');
        for (let i = 0; i < cookies.length; i++) {
            const cookie = cookies[i].trim();
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}

function validateVarietyForm() {
    clearErrors();
    let isValid = true;

    const skuPrefix = document.getElementById('sku_prefix').value.trim();
    if (!skuPrefix) {
        showError('sku_prefix', 'SKU Prefix is required');
        isValid = false;
    }

    return isValid;
}

function validateProductForm() {
    clearErrors();
    let isValid = true;

    const skuSuffix = document.getElementById('sku_suffix').value.trim();
    if (!skuSuffix) {
        showError('sku_suffix', 'SKU Suffix is required');
        isValid = false;
    }

    return isValid;
}

function validateWholesalePriceForm() {
    clearErrors();
    let isValid = true;

    const year = document.getElementById('price_year').value;
    const price = document.getElementById('price_per_packet').value;

    if (!year || year < 0 || year > 99) {
        showError('year', 'Please enter a valid 2-digit year (0-99)');
        isValid = false;
    }

    if (!price || parseFloat(price) < 0) {
        showError('price_per_packet', 'Please enter a valid price');
        isValid = false;
    }

    return isValid;
}

// Wholesale Price Form Submission
document.getElementById('wholesalePriceForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    if (!validateWholesalePriceForm()) {
        return;
    }

    const formData = new FormData();
    formData.append('year', document.getElementById('price_year').value);
    formData.append('price_per_packet', document.getElementById('price_per_packet').value);

    try {
        const response = await fetch(window.appUrls.setWholesalePrice, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            },
        });

        const data = await response.json();

        if (response.ok) {
            showSuccessMessage('wholesalePriceSuccessMessage');
            setTimeout(() => {
                closeWholesalePriceModal();
            }, 2000);
        } else {
            if (data.errors) {
                for (const [field, errors] of Object.entries(data.errors)) {
                    showError(field, errors[0]);
                }
            } else {
                alert('Error setting price: ' + (data.message || 'Unknown error'));
            }
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Network error occurred. Please try again.');
    }
});

// Variety Form Submission
document.getElementById('varietyForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    if (!validateVarietyForm()) {
        return;
    }

    const formData = new FormData();
    const form = document.getElementById('varietyForm');
    
    for (const element of form.elements) {
        if (element.name && element.type !== 'submit') {
            if (element.type === 'checkbox') {
                formData.append(element.name, element.checked);
            } else {
                formData.append(element.name, element.value);
            }
        }
    }

    try {
        const response = await fetch(window.appUrls.addVariety, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            },
        });

        const data = await response.json();

        if (response.ok) {
            showSuccessMessage('varietySuccessMessage');
            setTimeout(() => {
                closeVarietyModal();
                openProductModal(data.variety);
            }, 1500);
        } else {
            if (data.errors) {
                for (const [field, errors] of Object.entries(data.errors)) {
                    showError(field, errors[0]);
                }
            } else {
                alert('Error creating variety: ' + (data.message || 'Unknown error'));
            }
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Network error occurred. Please try again.');
    }
});

// Product Form Submission
document.getElementById('productForm').addEventListener('submit', async function(e) {
    e.preventDefault();
    
    if (!validateProductForm()) {
        return;
    }

    const formData = new FormData();
    const form = document.getElementById('productForm');
    
    formData.append('variety_id', currentVarietyId);
    
    for (const element of form.elements) {
        if (element.name && element.type !== 'submit' && element.name !== 'variety') {
            if (element.type === 'checkbox') {
                formData.append(element.name, element.checked);
            } else if (element.value !== '') {
                formData.append(element.name, element.value);
            }
        }
    }

    try {
        const response = await fetch(window.appUrls.addProduct, {
            method: 'POST',
            body: formData,
            headers: {
                'X-CSRFToken': getCookie('csrftoken'),
            },
        });

        const data = await response.json();

        if (response.ok) {
            showSuccessMessage('productSuccessMessage');
            setTimeout(() => {
                closeProductModal();
            }, 1500);
        } else {
            if (data.errors) {
                for (const [field, errors] of Object.entries(data.errors)) {
                    showError(field, errors[0]);
                }
            } else {
                alert('Error creating product: ' + (data.message || 'Unknown error'));
            }
        }
    } catch (error) {
        console.error('Error:', error);
        alert('Network error occurred. Please try again.');
    }
});

// Close modals when clicking outside
document.getElementById('systemSettingsModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeSystemSettingsModal();
    }
});

document.getElementById('wholesalePriceModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeWholesalePriceModal();
    }
});

document.getElementById('varietyModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeVarietyModal();
    }
});

document.getElementById('productModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeProductModal();
    }
});

// Close modals with Escape key
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        if (document.getElementById('systemSettingsModal').classList.contains('active')) {
            closeSystemSettingsModal();
        }
        if (document.getElementById('wholesalePriceModal').classList.contains('active')) {
            closeWholesalePriceModal();
        }
        if (document.getElementById('varietyModal').classList.contains('active')) {
            closeVarietyModal();
        }
        if (document.getElementById('productModal').classList.contains('active')) {
            closeProductModal();
        }
    }
});