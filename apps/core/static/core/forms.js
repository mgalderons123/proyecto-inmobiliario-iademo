(function () {
  "use strict";

  function focusErrorSummary() {
    var summary = document.querySelector("[data-form-error-summary]");
    if (summary) summary.focus();
  }

  function enableSubmitFeedback() {
    document.querySelectorAll("form[data-submit-feedback]").forEach(function (form) {
      form.addEventListener("submit", function (event) {
        if (form.dataset.submitting === "true") {
          event.preventDefault();
          return;
        }
        form.dataset.submitting = "true";
        var submitter = form.querySelector('button[type="submit"], input[type="submit"]');
        if (!submitter) return;
        submitter.setAttribute("aria-disabled", "true");
        submitter.classList.add("is-loading");
        var loadingLabel = submitter.getAttribute("data-loading-label");
        if (loadingLabel && submitter.tagName === "BUTTON") {
          submitter.dataset.originalLabel = submitter.textContent;
          submitter.textContent = loadingLabel;
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", function () {
    focusErrorSummary();
    enableSubmitFeedback();
  });
})();
