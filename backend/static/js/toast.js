function showToast(message, type = 'info') {
    // Create toast element if it doesn't exist
    let toast = document.getElementById('toast-notification');
    if (!toast) {
        toast = document.createElement('div');
        toast.id = 'toast-notification';
        toast.className = 'toast';
        document.body.appendChild(toast);
    }

    // Set message and type
    toast.textContent = message;
    toast.className = `toast show ${type}`;

    // Hide after 3 seconds
    setTimeout(function () {
        toast.className = toast.className.replace('show', '');
    }, 3000);
}
