// Growouts JavaScript Functionality

let currentEditingLotId = null;
let allRows = []; // Store all table rows for filtering

// Initialize page
// Initialize page
document.addEventListener('DOMContentLoaded', function() {
    // Store all table rows
    allRows = Array.from(document.querySelectorAll('#tableBody tr'));
    
    // Reset filters on page load
    document.getElementById('categorySelect').value = '';
    document.getElementById('growerSelect').value = '';
    
    // Set up filter event listeners
    document.getElementById('yearSelect').addEventListener('change', handleYearChange);
    document.getElementById('categorySelect').addEventListener('change', handleCategoryChange);
    document.getElementById('growerSelect').addEventListener('change', handleGrowerChange);
    
    // NEW: Auto-select most recent year if no year parameter in URL
    const urlParams = new URLSearchParams(window.location.search);
    if (!urlParams.has('year')) {
        setDefaultYear();
    }
});

// NEW: Function to set the most recent year as default
function setDefaultYear() {
    const yearSelect = document.getElementById('yearSelect');
    const yearOptions = Array.from(yearSelect.options);
    
    // Find the highest year (skip the first option which is usually "Select Year" or empty)
    const yearValues = yearOptions
        .slice(1) // Skip first option
        .map(option => parseInt(option.value))
        .filter(year => !isNaN(year));
    
    if (yearValues.length > 0) {
        const mostRecentYear = Math.max(...yearValues);
        yearSelect.value = mostRecentYear;
        
        // Trigger the change event to reload with the selected year
        handleYearChange({ target: { value: mostRecentYear } });
    }
}

function handleYearChange(e) {
    const selectedYear = e.target.value;
    if (selectedYear) {
        // Reset other filters
        document.getElementById('categorySelect').value = '';
        document.getElementById('growerSelect').value = '';
        // Reload page with selected year
        window.location.href = `?year=${selectedYear}`;
    }
}

function handleCategoryChange(e) {
    applyFilters();
}

function handleGrowerChange(e) {
    applyFilters();
}

function applyFilters() {
    const categoryFilter = document.getElementById('categorySelect').value;
    const growerFilter = document.getElementById('growerSelect').value;
    
    let visibleCount = 0;
    
    allRows.forEach(row => {
        const rowCategory = row.dataset.category;
        const rowGrower = row.dataset.grower;
        
        let showRow = true;
        
        // Apply category filter
        if (categoryFilter && rowCategory !== categoryFilter) {
            showRow = false;
        }
        
        // Apply grower filter
        if (growerFilter && rowGrower !== growerFilter) {
            showRow = false;
        }
        
        if (showRow) {
            row.style.display = '';
            visibleCount++;
        } else {
            row.style.display = 'none';
        }
    });
    
    // Update count
    document.getElementById('growoutCount').textContent = `${visibleCount} lots`;
}

function openEditModal(lotId) {
    currentEditingLotId = parseInt(lotId);
    const row = document.querySelector(`tr[data-lot-id="${lotId}"]`);
    
    if (!row) {
        console.error('Row not found for lot ID:', lotId);
        return;
    }
    
    // Get current values from the row
    const varietyName = row.dataset.variety;
    const lotCode = row.querySelector('.lot-cell').textContent;
    
    // Update modal subtitle
    document.getElementById('editModalSubtitle').textContent = `${varietyName} - Lot ${lotCode}`;
    
    // Helper function to get cell value
    function getCellValue(fieldName) {
        const cell = row.querySelector(`[data-field="${fieldName}"]`);
        if (!cell) return '';
        
        // For notes, use title attribute to get full text (not truncated)
        if (fieldName === 'notes') {
            const titleValue = cell.getAttribute('title');
            return titleValue && titleValue.trim() !== '' ? titleValue.trim() : '';
        }
        
        // For other fields, use text content
        const textValue = cell.textContent.trim();
        return textValue === '—' ? '' : textValue;
    }
    
    // Map field names to input IDs and prefill
    const fieldMappings = {
        'planted_date': 'editPlantedDate',
        'transplant_date': 'editTransplantDate',
        'quantity': 'editQuantity',
        'price_per_lb': 'editPricePerLb',
        'bed_ft': 'editBedFt',
        'amt_sown': 'editAmtSown',
        'notes': 'editNotes'
    };
    
    // Prefill form with current values
    Object.entries(fieldMappings).forEach(([fieldName, inputId]) => {
        const input = document.getElementById(inputId);
        if (input) {
            const value = getCellValue(fieldName);
            input.value = value;
            console.log(`Set ${inputId} to: "${value}"`); // Debug log
        }
    });
    
    // Show modal
    document.getElementById('editModal').classList.add('visible');
}

function closeEditModal() {
    document.getElementById('editModal').classList.remove('visible');
    currentEditingLotId = null;
    document.getElementById('editForm').reset();
}

function saveGrowout() {
    if (!currentEditingLotId) return;
    
    const saveBtn = document.getElementById('saveBtn');
    const originalText = saveBtn.textContent;
    
    // Show loading state
    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';
    document.body.classList.add('processing');
    
    // Collect form data
    const formData = {
        planted_date: document.getElementById('editPlantedDate').value,
        transplant_date: document.getElementById('editTransplantDate').value,
        quantity: document.getElementById('editQuantity').value,
        price_per_lb: document.getElementById('editPricePerLb').value,
        bed_ft: document.getElementById('editBedFt').value,
        amt_sown: document.getElementById('editAmtSown').value,
        notes: document.getElementById('editNotes').value
    };
    
    // Send to backend
    fetch(`/office/update-growout/${currentEditingLotId}/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrftoken'),
        },
        body: JSON.stringify(formData)
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Close modal
            closeEditModal();
            // Reload page to show updated data
            location.reload();
        } else {
            alert('Error saving changes: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        alert('Network error while saving changes.');
    })
    .finally(() => {
        saveBtn.disabled = false;
        saveBtn.textContent = originalText;
        document.body.classList.remove('processing');
    });
}

// Close modal when clicking overlay
document.getElementById('editModal').addEventListener('click', function(e) {
    if (e.target === this) {
        closeEditModal();
    }
});

// CSRF token helper
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