// CSRF token helper - read from meta tag
function getCSRFToken() {
    return document.querySelector('meta[name="csrf-token"]')?.content || '';
}

// Toast notification system
function showToast(type, title, message, duration = 5000) {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    
    const icons = {
        success: '✅',
        error: '❌',
        warning: '⚠️',
        info: 'ℹ️'
    };
    
    toast.innerHTML = `
        <div class="toast-icon">${icons[type] || icons.info}</div>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            <div class="toast-message">${message}</div>
        </div>
        <button class="toast-close" onclick="closeToast(this)">&times;</button>
    `;
    
    container.appendChild(toast);
    
    setTimeout(() => toast.classList.add('show'), 100);
    setTimeout(() => closeToast(toast.querySelector('.toast-close')), duration);
}

function closeToast(button) {
    const toast = button.closest('.toast');
    toast.classList.remove('show');
    setTimeout(() => toast.remove(), 400);
}


function checkAdminAccess() {
    fetch(window.appUrls.checkAdmin, {  // Changed this line
        method: 'GET',
        headers: {
            'X-CSRFToken': getCSRFToken(),
        }
    })
    .then(response => response.json())
    .then(data => {
        if (data.is_admin) {
            window.location.href = window.appUrls.adminDashboard;  // Changed this line
        } else {
            showToast('error', 'Access Denied', 'You are not authorized to access the admin dashboard. Please contact an administrator if you need access.');
        }
    })
    .catch(error => {
        console.error('Error checking admin access:', error);
        showToast('error', 'Error', 'Unable to verify admin access. Please try again.');
    });
}

async function handleAddressLabels() {
    const button = document.querySelector('.address-labels-button');
    button.disabled = true;
    button.textContent = 'Checking...';
    
    try {
        console.log('Checking Flask health for address labels...');
        
        const healthResponse = await fetch('http://127.0.0.1:5000/health', {
            method: 'GET'
        });
        
        if (!healthResponse.ok) {
            throw new Error('Flask health check failed');
        }
        
        console.log('Flask is healthy, sending print request...');
        
        const printResponse = await fetch('http://127.0.0.1:5000/print-address-labels', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!printResponse.ok) {
            throw new Error('Address labels print request failed');
        }
        
        const result = await printResponse.json();
        
        if (result.success) {
            showToast('success', 'Print Successful', result.message || 'Address labels sent to printer.');
        } else {
            showToast('error', 'Print Failed', result.error || 'Failed to print address labels.');
        }
        
    } catch (error) {
        console.error('Address labels error:', error);
        
        let errorTitle = 'Print Service Error';
        let errorMessage = 'An unexpected error occurred.';
        
        if (error.message.includes('Flask health check failed') || 
            error.message.includes('Failed to fetch') ||
            error.name === 'TypeError') {
            errorTitle = 'Print Service Unavailable';
            errorMessage = 'The printing service is not currently running. Please start the Flask print service and try again.';
        } else if (error.message.includes('print request failed')) {
            errorTitle = 'Print Request Failed';
            errorMessage = 'The print service encountered an error while processing your request.';
        }
        
        showToast('error', errorTitle, errorMessage, 8000);
        
    } finally {
        button.disabled = false;
        button.textContent = 'Address Labels';
    }
}

function showInventoryMenu() {
    document.getElementById('inventoryMenu').style.display = 'flex';
}

function closeInventoryMenu() {
    document.getElementById('inventoryMenu').style.display = 'none';
}

function showWholesaleMenu() {
    document.getElementById('wholesaleMenu').style.display = 'flex';
}

function closeWholesaleMenu() {
    document.getElementById('wholesaleMenu').style.display = 'none';
}

function showLogoutVerification() {
    document.getElementById('verifyLogout').style.display = 'flex';
}

function closeModal() {
    document.getElementById('verifyLogout').style.display = 'none';
}

function logout() {
    const form = document.createElement('form');
    form.method = 'POST';
    form.action = window.appUrls.logout || '/accounts/logout/';  // Changed this line

    let csrfToken = getCSRFToken();
    if (csrfToken) {
        const csrfHidden = document.createElement('input');
        csrfHidden.type = 'hidden';
        csrfHidden.name = 'csrfmiddlewaretoken';
        csrfHidden.value = csrfToken;
        form.appendChild(csrfHidden);
    }

    document.body.appendChild(form);
    form.submit();
}

document.addEventListener('DOMContentLoaded', function() {
    const wholesaleCard = document.querySelector('.wholesale-card');
    const inventoryCard = document.querySelector('.inventory-card');
    const logoutButton = document.querySelector('.logout-button');

    if (wholesaleCard) wholesaleCard.addEventListener('click', showWholesaleMenu);
    if (inventoryCard) inventoryCard.addEventListener('click', showInventoryMenu);
    if (logoutButton) logoutButton.addEventListener('click', showLogoutVerification);

    document.addEventListener('click', function(event) {
        const logoutModal = document.getElementById('verifyLogout');
        const wholesaleModal = document.getElementById('wholesaleMenu');
        const inventoryModal = document.getElementById('inventoryMenu');

        if (event.target === logoutModal) closeModal();
        if (event.target === wholesaleModal) closeWholesaleMenu();
        if (event.target === inventoryModal) closeInventoryMenu();
    });

    document.addEventListener('keydown', function(event) {
        if (event.key === 'Escape') {
            closeModal();
            closeWholesaleMenu();
            closeInventoryMenu();
        }
    });
});