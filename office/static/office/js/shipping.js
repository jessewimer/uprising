// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    initializeShippingPage();
});

function initializeShippingPage() {
    // Year filter functionality
    const yearSelect = document.getElementById('yearSelect');
    if (yearSelect) {
        yearSelect.addEventListener('change', filterByYear);
    }

    // QuickBooks checkbox functionality
    const checkboxes = document.querySelectorAll('.quickbooks-checkbox');
    checkboxes.forEach(checkbox => {
        checkbox.addEventListener('change', handleQuickBooksToggle);
    });

    // Trigger filter on page load to show only the selected year
    if (yearSelect && yearSelect.value) {
        filterByYear.call(yearSelect);
    }
}

/**
 * Filter table rows by selected year
 */

function filterByYear() {
    const selectedYear = this.value;
    const tableRows = document.querySelectorAll('#ordersTableBody tr[data-year]');
    
    tableRows.forEach(row => {
        if (!selectedYear) {
            // Show all rows if no year is selected
            row.style.display = '';
        } else {
            // Show only rows matching the selected year
            const rowYear = row.getAttribute('data-year');
            // Compare last 2 digits of selected year with row year
            const selectedYearSuffix = selectedYear.slice(-2);
            if (rowYear === selectedYearSuffix) {
                row.style.display = '';
            } else {
                row.style.display = 'none';
            }
        }
    });
}


/**
 * Handle QuickBooks checkbox toggle with AJAX
 */
function handleQuickBooksToggle(event) {
    const checkbox = event.target;
    const orderId = checkbox.getAttribute('data-order-id');
    const isChecked = checkbox.checked;

    // Disable checkbox during request
    checkbox.disabled = true;

    // Send AJAX request to update database
    fetch('/office/ajax/update-quickbooks/', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCsrfToken()
        },
        body: JSON.stringify({
            order_id: orderId,
            quickbooks_invoice: isChecked
        })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            // Show success message
            showSuccessMessage(`QuickBooks status updated for order ${data.order_number}`);
            // Re-enable checkbox
            checkbox.disabled = false;
        } else {
            // Revert checkbox on error
            checkbox.checked = !isChecked;
            checkbox.disabled = false;
            alert('Error updating QuickBooks status: ' + (data.error || 'Unknown error'));
        }
    })
    .catch(error => {
        console.error('Error:', error);
        // Revert checkbox on error
        checkbox.checked = !isChecked;
        checkbox.disabled = false;
        alert('Error updating QuickBooks status. Please try again.');
    });
}

/**
 * Get CSRF token from cookie
 */
function getCsrfToken() {
    const name = 'csrftoken';
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

/**
 * Show success message with auto-hide
 */
function showSuccessMessage(message) {
    const successDiv = document.getElementById('successMessage');
    if (successDiv) {
        successDiv.textContent = message;
        successDiv.classList.add('show');
        
        // Auto-hide after 3 seconds
        setTimeout(() => {
            successDiv.classList.remove('show');
        }, 3000);
    }
}