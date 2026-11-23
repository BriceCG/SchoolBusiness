/** Show only the states of the selected country in the admission form. */
document.addEventListener("DOMContentLoaded", () => {
    const country = document.querySelector("#school_admission_form select[name='country_id']");
    const state = document.querySelector("#school_admission_form select[name='state_id']");
    if (!country || !state) {
        return;
    }
    const refresh = () => {
        let hasMatch = false;
        for (const option of state.options) {
            const match = !option.value || option.dataset.countryId === country.value;
            option.hidden = !match;
            option.disabled = !match;
            hasMatch = hasMatch || (match && !!option.value);
        }
        if (state.selectedOptions[0] && state.selectedOptions[0].disabled) {
            state.value = "";
        }
        state.closest(".school_state_wrapper").classList.toggle("d-none", !hasMatch);
    };
    country.addEventListener("change", refresh);
    refresh();
});
