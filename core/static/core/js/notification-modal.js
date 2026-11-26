function inicializarModalNotificaciones() {
    document.querySelectorAll('[data-notification-modal]').forEach((modal) => {
        if (modal.dataset.notificationReady) return;
        modal.dataset.notificationReady = 'true';

        modal.querySelectorAll('[data-notification-close]').forEach((button) => {
            button.addEventListener('click', () => modal.close());
        });
        modal.addEventListener('click', (event) => {
            if (event.target === modal) modal.close();
        });

        if (modal.querySelector('[data-notification-item]') && !modal.open) {
            modal.showModal();
        }
    });
}

document.addEventListener('DOMContentLoaded', inicializarModalNotificaciones);
document.addEventListener('piemonte:contenido-actualizado', inicializarModalNotificaciones);
