// Growout Prep JavaScript

let allRows = [];
let hasUnsavedChanges = false;

// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    allRows = Array.from(document.querySelectorAll('#tableBody tr'));
    
    // Set up filter event listeners
    document.getElementById('statusFilter').addEventListener('change', applyFilters);
    document.getElementById('categoryFilter').addEventListener('change', applyFilters);
    document.getElementById('cropFilter').addEventListener('change', applyFilters);
    
    // Set up grower select change handlers
    document.querySelectorAll('.grower-select').forEach(select => {
        select.addEventListener('change', handleInputChange);
    });
});

function applyFilters() {
    const statusFilter = document.getElementById('statusFilter').value;
    const categoryFilter = document.getElementById('categoryFilter').value;
    const cropFilter = document.getElementById('cropFilter').value;
    
    let visibleCount = 0;
    
    allRows.forEach(row => {
        const rowStatus = row.dataset.status;
        const rowCategory = row.dataset.category;
        const rowCrop = row.dataset.crop;
        
        let showRow = true;
        
        if (statusFilter && rowStatus !== statusFilter) {
            showRow = false;
        }
        
        if (categoryFilter && rowCategory !== categoryFilter) {
            showRow = false;
        }
        
        if (cropFilter && rowCrop !== cropFilter) {
            showRow = false;
        }
        
        if (showRow) {
            row.style.display = '';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });
    
    document.getElementById('varietyCount').textContent = `${visibleCount} varieties`;
}

function decreaseYear(button) {
    const varietyId = button.dataset.varietyId;
    const row = button.closest('tr');
    const input = row.querySelector('.year-input');
    const minYear = parseInt(input.dataset.minYear);
    let currentYear = parseInt(input.value);
    
    if (currentYear > minYear) {
        input.value = currentYear - 1;
        handleInputChange();
    }
}

function increaseYear(button) {
    const varietyId = button.dataset.varietyId;
    const row = button.closest('tr');
    const input = row.querySelector('.year-input');
    let currentYear = parseInt(input.value);
    
    input.value = currentYear + 1;
    handleInputChange();
}

function toggleCreateLot(button) {
    const isCreated = button.dataset.created === 'true';
    
    if (isCreated) {
        // Switch back to X
        button.textContent = '✗';
        button.dataset.created = 'false';
        button.classList.remove('created');
    } else {
        // Switch to checkmark
        button.textContent = '✓';
        button.dataset.created = 'true';
        button.classList.add('created');
    }
    
    handleInputChange();
}

function handleInputChange() {
    hasUnsavedChanges = true;
    const saveBtn = document.getElementById('saveChangesBtn');
    saveBtn.disabled = false;
    saveBtn.classList.add('active');
}

function saveChanges() {
    // Placeholder for backend call
    console.log('Save changes clicked - collecting data...');
    
    const changedData = [];
    
    allRows.forEach(row => {
        const varietyId = row.dataset.varietyId;
        const varietyName = row.dataset.varietyName;
        const skuPrefix = row.dataset.skuPrefix;
        
        const growerSelect = row.querySelector('.grower-select');
        const yearInput = row.querySelector('.year-input');
        const createLotBtn = row.querySelector('.create-lot-btn');
        const qtyInput = row.querySelector('.qty-input');
        const priceInput = row.querySelector('.price-input');
        
        const rowData = {
            variety_id: varietyId,
            variety_name: varietyName,
            sku_prefix: skuPrefix,
            grower: growerSelect.value,
            year: yearInput.value,
            create_lot: createLotBtn.dataset.created === 'true',
            quantity: qtyInput.value,
            price_per_lb: priceInput.value
        };
        
        // Only include rows with some data
        if (rowData.grower || rowData.quantity || rowData.price_per_lb || rowData.create_lot) {
            changedData.push(rowData);
        }
    });
    
    console.log('Data to save:', changedData);
    
    // TODO: Implement actual backend call here
    // fetch('/office/save-growout-prep/', {
    //     method: 'POST',
    //     headers: {
    //         'Content-Type': 'application/json',
    //         'X-CSRFToken': window.appData.csrfToken
    //     },
    //     body: JSON.stringify({ data: changedData })
    // })
    // .then(response => response.json())
    // .then(data => {
    //     if (data.success) {
    //         alert('Changes saved successfully!');
    //         resetSaveButton();
    //     }
    // });
    
    // For now, just show alert
    alert(`Would save ${changedData.length} rows of data (see console for details)`);
    resetSaveButton();
}

function resetSaveButton() {
    hasUnsavedChanges = false;
    const saveBtn = document.getElementById('saveChangesBtn');
    saveBtn.disabled = true;
    saveBtn.classList.remove('active');
}

// CSRF token helper
function getCSRFToken() {
    return window.appData.csrfToken || '';
}