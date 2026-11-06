(function () {
  "use strict";

  var body = document.body;
  var sidebar = document.getElementById("sidebar");
  var mobileOpen = document.getElementById("mobileNavOpen");
  var backdrop = document.getElementById("sidebarBackdrop");
  var lastNavTrigger = null;

  function setMobileNav(open) {
    body.classList.toggle("nav-open", open);
    if (mobileOpen) mobileOpen.setAttribute("aria-expanded", open ? "true" : "false");
    if (backdrop) backdrop.hidden = !open;
    if (open && sidebar) {
      lastNavTrigger = document.activeElement;
      var first = sidebar.querySelector("a, button");
      if (first) first.focus();
    } else if (lastNavTrigger && typeof lastNavTrigger.focus === "function") {
      lastNavTrigger.focus();
    }
  }

  if (mobileOpen) mobileOpen.addEventListener("click", function () { setMobileNav(true); });
  if (backdrop) backdrop.addEventListener("click", function () { setMobileNav(false); });

  document.querySelectorAll("[data-nav-section]").forEach(function (button) {
    var panel = document.getElementById(button.getAttribute("aria-controls"));
    if (!panel) return;
    button.addEventListener("click", function () {
      var open = button.getAttribute("aria-expanded") === "true";
      button.setAttribute("aria-expanded", open ? "false" : "true");
      panel.hidden = open;
    });
  });

  var userButton = document.querySelector("[data-user-menu]");
  if (userButton) {
    var userMenu = document.getElementById(userButton.getAttribute("aria-controls"));
    userButton.addEventListener("click", function () {
      var open = userButton.getAttribute("aria-expanded") === "true";
      userButton.setAttribute("aria-expanded", open ? "false" : "true");
      if (userMenu) userMenu.hidden = open;
    });
  }

  document.addEventListener("keydown", function (event) {
    if (event.key === "Escape" && body.classList.contains("nav-open")) setMobileNav(false);
  });

  document.querySelectorAll(".sidebar__nav a").forEach(function (link) {
    if (link.pathname === window.location.pathname) {
      link.setAttribute("aria-current", "page");
      var subnav = link.closest(".sidebar__subnav");
      if (subnav) {
        subnav.hidden = false;
        var trigger = document.querySelector('[aria-controls="' + subnav.id + '"]');
        if (trigger) trigger.setAttribute("aria-expanded", "true");
      }
    }
  });

  var desktopToggle = document.getElementById("sidebarToggle");
  var layout = document.getElementById("layout");
  if (desktopToggle && layout) {
    var key = "sidebarCollapsed";
    function applyCollapsed(collapsed) {
      layout.classList.toggle("layout--collapsed", collapsed);
      desktopToggle.setAttribute("aria-expanded", collapsed ? "false" : "true");
      desktopToggle.setAttribute("aria-label", collapsed ? body.dataset.showMenu : body.dataset.hideMenu);
      desktopToggle.title = collapsed ? body.dataset.showMenu : body.dataset.hideMenu;
    }
    applyCollapsed(localStorage.getItem(key) === "1");
    desktopToggle.addEventListener("click", function () {
      var collapsed = !layout.classList.contains("layout--collapsed");
      localStorage.setItem(key, collapsed ? "1" : "0");
      applyCollapsed(collapsed);
    });
  }

  var eyeOpen = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M2 12s3.5-6 10-6 10 6 10 6-3.5 6-10 6S2 12 2 12Z"/><circle cx="12" cy="12" r="3"/></svg>';
  var eyeClosed = '<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="m3 3 18 18M10.6 10.7a2 2 0 0 0 2.7 2.7M9.8 5.2A11 11 0 0 1 12 5c6.5 0 10 7 10 7a17 17 0 0 1-2.1 3M6.5 6.5C3.5 8.4 2 12 2 12s3.5 7 10 7a10 10 0 0 0 4-.8"/></svg>';
  document.querySelectorAll('input[type="password"]').forEach(function (input) {
    if (input.closest(".password-control")) return;
    var wrapper = document.createElement("div");
    wrapper.className = "password-control";
    input.parentNode.insertBefore(wrapper, input);
    wrapper.appendChild(input);
    var button = document.createElement("button");
    button.type = "button";
    button.className = "password-toggle";
    button.setAttribute("aria-pressed", "false");
    button.setAttribute("aria-label", body.dataset.showPassword);
    button.title = body.dataset.showPassword;
    button.innerHTML = eyeOpen;
    button.addEventListener("click", function () {
      var visible = input.type === "text";
      input.type = visible ? "password" : "text";
      button.setAttribute("aria-pressed", visible ? "false" : "true");
      button.setAttribute("aria-label", visible ? body.dataset.showPassword : body.dataset.hidePassword);
      button.title = visible ? body.dataset.showPassword : body.dataset.hidePassword;
      button.innerHTML = visible ? eyeOpen : eyeClosed;
      input.focus();
    });
    wrapper.appendChild(button);
  });
})();
