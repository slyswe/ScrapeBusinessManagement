document.addEventListener('DOMContentLoaded', () => {
    // Handle search filter form submission
    const searchForm = document.querySelector('#search-form');
    if (searchForm) {
        searchForm.addEventListener('submit', (e) => {
            e.preventDefault();
            const formData = new FormData(searchForm);
            const queryString = new URLSearchParams(formData).toString();
            window.location.href = `/financial-report/?${queryString}`;
        });
    }
});