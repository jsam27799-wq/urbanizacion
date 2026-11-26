(() => {
    const widget = document.querySelector('[data-floating-help]');
    if (!widget) return;

    const button = widget.querySelector('[data-floating-help-toggle]');
    const menu = widget.querySelector('[data-floating-help-menu]');
    const manualButton = widget.querySelector('[data-manual-open]');
    const manualDialog = widget.querySelector('[data-manual-dialog]');
    const manualCloseButton = widget.querySelector('[data-manual-close]');
    if (!button || !menu) return;

    const setMenuOpen = (open) => {
        menu.hidden = !open;
        button.setAttribute('aria-expanded', String(open));
        button.setAttribute('aria-label', open ? 'Cerrar opciones de ayuda' : 'Abrir opciones de ayuda');
        button.classList.toggle('is-open', open);
    };

    button.addEventListener('click', () => {
        const abierto = button.getAttribute('aria-expanded') === 'true';
        setMenuOpen(!abierto);
    });

    if (manualButton && manualDialog && manualCloseButton) {
        manualButton.addEventListener('click', () => {
            setMenuOpen(false);
            manualDialog.showModal();
        });

        manualCloseButton.addEventListener('click', () => manualDialog.close());

        manualDialog.addEventListener('click', (event) => {
            if (event.target === manualDialog) manualDialog.close();
        });
    }

    document.addEventListener('click', (event) => {
        if (!widget.contains(event.target)) setMenuOpen(false);
    });

    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape') setMenuOpen(false);
    });
})();
