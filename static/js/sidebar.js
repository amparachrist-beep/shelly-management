// static/js/sidebar.js

document.addEventListener('DOMContentLoaded', function() {
    const toggleButtons = document.querySelectorAll('.sidebar-toggle');

    toggleButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            e.preventDefault();

            const targetId = this.getAttribute('data-target');
            const submenu = document.getElementById(targetId);
            const chevron = this.querySelector('.chevron');

            // Fermer tous les autres sous-menus
            document.querySelectorAll('.submenu').forEach(menu => {
                if (menu.id !== targetId && !menu.classList.contains('hidden')) {
                    menu.classList.add('hidden');
                    const otherButton = document.querySelector(`[data-target="${menu.id}"]`);
                    if (otherButton) {
                        otherButton.classList.remove('text-orange-500', 'bg-orange-500/10');
                        otherButton.classList.add('text-slate-400');
                        const otherChevron = otherButton.querySelector('.chevron');
                        if (otherChevron) {
                            otherChevron.style.transform = 'rotate(0deg)';
                        }
                    }
                }
            });

            // Toggle le sous-menu actuel
            if (submenu && submenu.classList.contains('hidden')) {
                submenu.classList.remove('hidden');
                this.classList.remove('text-slate-400');
                this.classList.add('text-orange-500', 'bg-orange-500/10');
                if (chevron) {
                    chevron.style.transform = 'rotate(180deg)';
                }
            } else if (submenu) {
                submenu.classList.add('hidden');
                this.classList.remove('text-orange-500', 'bg-orange-500/10');
                this.classList.add('text-slate-400');
                if (chevron) {
                    chevron.style.transform = 'rotate(0deg)';
                }
            }
        });
    });
});