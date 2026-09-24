/* =========================================================
   CEMS Student Portal — Registration wizard (enhanced)
   Self-contained controller for student_register.html.
   Keeps field names / IDs / endpoint behaviour intact while
   adding: smooth scroll to errors, an animated stepper, and
   polished password + photo interactions.
   ========================================================= */
(function () {
  "use strict";

  /* ---------- DOM references ---------- */
  var form = document.getElementById("student-register-form");
  if (!form) return;

  var errorContainer = document.getElementById("register-error-container");
  var submitBtn = document.getElementById("student-register-submit");
  var nextBtn = document.getElementById("student-step-next");
  var backBtn = document.getElementById("student-step-back");
  var stepIndicator = document.getElementById("student-step-indicator");
  var passwordInput = document.getElementById("reg-password");
  var confirmInput = document.getElementById("reg-confirm-password");
  var photoInput = document.getElementById("reg-photo");
  var photoArea = document.getElementById("photo-upload-area");
  var photoPlaceholder = document.getElementById("photo-placeholder");
  var photoPreview = document.getElementById("photo-preview");
  var photoRemove = document.getElementById("photo-remove");

  var validateUrl = form.dataset.validateUrl || "/api/register/validate-step";
  var TOTAL_STEPS = 4;
  var currentStep = 1;
  var submitted = false; /* blocks double submit */

  var STEP_FIELDS = {
    1: ["name", "email", "mobile", "date_of_birth"],
    2: ["student_id", "roll_no"],
    3: ["course", "department", "semester", "section", "academic_session", "batch"],
    4: ["password", "confirm_password"]
  };

  /* ---------- Step navigation ---------- */
  function showStep(step) {
    currentStep = step;
    var sections = document.querySelectorAll(".sp-section");
    sections.forEach(function (s) {
      s.classList.toggle("active", Number(s.dataset.step) === step);
    });

    var steps = document.querySelectorAll("#student-stepper .sp-step");
    steps.forEach(function (item) {
      var s = Number(item.dataset.step);
      item.classList.remove("active", "completed");
      var circle = item.querySelector(".sp-step-circle");
      if (!circle) return;
      if (s === step) {
        item.classList.add("active");
        circle.innerHTML = "<span>" + s + "</span>";
      } else if (s < step) {
        item.classList.add("completed");
        circle.innerHTML = '<svg fill="none" stroke="currentColor" viewBox="0 0 24 24" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><path d="M5 13l4 4L19 7"/></svg>';
      } else {
        circle.innerHTML = "<span>" + s + "</span>";
      }
    });

    var connectors = document.querySelectorAll("#student-stepper .sp-step-connector");
    connectors.forEach(function (conn, i) {
      conn.classList.toggle("completed", i < step - 1);
    });

    if (stepIndicator) stepIndicator.textContent = "Step " + step + " of " + TOTAL_STEPS;
    if (backBtn) backBtn.style.display = step > 1 ? "" : "none";
    if (nextBtn && submitBtn) {
      if (step === TOTAL_STEPS) {
        nextBtn.style.display = "none";
        submitBtn.style.display = "";
      } else {
        nextBtn.style.display = "";
        submitBtn.style.display = "none";
      }
    }
  }

  /* ---------- Error rendering / scrolling ---------- */
  function clearErrors() {
    if (errorContainer) errorContainer.innerHTML = "";
    form.querySelectorAll(".sp-control.has-error").forEach(function (el) {
      el.classList.remove("has-error");
    });
    form.querySelectorAll(".sp-field-error").forEach(function (el) {
      el.remove();
    });
  }

  function renderErrors(errors) {
    if (!errorContainer) return;
    errorContainer.innerHTML = "";
    Object.keys(errors || {}).forEach(function (field) {
      var bar = document.createElement("div");
      bar.className = "sp-error";
      bar.dataset.field = field;
      bar.textContent = errors[field];
      errorContainer.appendChild(bar);

      var input = form.querySelector('[name="' + field + '"]');
      if (input && input.classList.contains("sp-control")) input.classList.add("has-error");

      var errorSpan = form.querySelector('[data-field="' + field + '"].sp-field-error');
      if (!errorSpan && input && input.tagName === "INPUT") {
        var err = document.createElement("span");
        err.className = "sp-field-error";
        err.setAttribute("data-field", field);
        err.textContent = errors[field];
        input.parentNode.appendChild(err);
      }
    });
    scrollToFirstError();
  }

  function scrollToFirstError() {
    var firstBar = errorContainer && errorContainer.querySelector(".sp-error");
    var target = firstBar || form.querySelector(".sp-control.has-error");
    if (!target) return;
    var top = target.getBoundingClientRect().top + window.pageYOffset;
    var offset = 90;
    var start = (window.pageYOffset || document.documentElement.scrollTop);
    var distance = top - start - offset;
    if (Math.abs(distance) < 30) {
      target.scrollIntoView({ behavior: "smooth", block: "nearest" });
      return;
    }
    var duration = 520;
    var startTime = null;
    var easeInOut = function (t) { return t < 0.5 ? 2 * t * t : -1 + (4 - 2 * t) * t; };
    function step() {
      if (!startTime) startTime = window.performance.now();
      var now = window.performance.now();
      var run = now - startTime;
      var pct = Math.min(run / duration, 1);
      window.scrollTo(0, start + distance * easeInOut(pct));
      if (pct < 1) window.requestAnimationFrame(step);
    }
    window.requestAnimationFrame(step);
  }

  /* ---------- Client-side validation (mirrors backend rules) ---------- */
  function validateCurrentStep() {
    var fields = STEP_FIELDS[currentStep] || [];
    var localErrors = {};

    fields.forEach(function (name) {
      var input = form.querySelector('[name="' + name + '"]');
      if (!input) return;
      var value = input.type === "file"
        ? (input.files && input.files.length ? input.files[0].name : "")
        : (input.value || "").trim();

      if (input.required && !value) {
        var label = "";
        if (input.labels && input.labels[0]) {
          label = input.labels[0].textContent.replace("*", "").replace("Optional", "").trim();
        }
        localErrors[name] = label
          ? (label + " is required.")
          : (name.replace(/_/g, " ") + " is required.");
        input.classList.add("has-error");
      } else if (name === "email" && value && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value)) {
        localErrors[name] = "Please enter a valid email address.";
        input.classList.add("has-error");
      } else if (name === "mobile" && value && !/^[+]?[6-9]\d{9,11}$/.test(value.replace(/[\s-]/g, ""))) {
        localErrors[name] = "Enter a valid Indian mobile number.";
        input.classList.add("has-error");
      } else if (name === "batch" && value && !/^(?:19|20)\d{2}(?:\s*[-–]\s*(?:19|20)\d{2})?$/.test(value)) {
        localErrors[name] = "Enter a valid batch year, for example 2024 or 2024–2028.";
        input.classList.add("has-error");
      } else if (name === "password" && value) {
        var pwd = value;
        var hasLetter = /[A-Za-z]/.test(pwd);
        var hasNumber = /[0-9]/.test(pwd);
        var hasSpecial = /[^A-Za-z0-9]/.test(pwd);
        if (pwd.length < 8) {
          localErrors[name] = "Password must be at least 8 characters.";
          input.classList.add("has-error");
        } else if (!hasLetter || !hasNumber || !hasSpecial) {
          localErrors[name] = "Password must include a letter, a number, and a special character.";
          input.classList.add("has-error");
        }
      } else if (name === "confirm_password" && value) {
        if (input.value !== (passwordInput ? passwordInput.value : "")) {
          localErrors[name] = "Passwords do not match.";
          input.classList.add("has-error");
        }
      } else {
        input.classList.remove("has-error");
      }
    });

    if (Object.keys(localErrors).length > 0) {
      renderErrors(localErrors);
      return false;
    }
    return true;
  }

  /* ---------- Wizard flow ---------- */
  function appendHiddenRole(fd) {
    fd.append("role", "student");
    return fd;
  }

  if (nextBtn) {
    nextBtn.addEventListener("click", function () {
      clearErrors();
      if (!validateCurrentStep()) return;

      var fd = appendHiddenRole(new FormData(form));
      fd.append("step", currentStep);

      nextBtn.disabled = true;
      nextBtn.style.opacity = "0.62";

      fetch(validateUrl, {
        method: "POST",
        body: fd,
        headers: { "X-Requested-With": "XMLHttpRequest" }
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          nextBtn.disabled = false;
          nextBtn.style.opacity = "";
          if (data && data.success) {
            showStep(currentStep + 1);
          } else if (data && data.errors) {
            renderErrors(data.errors);
          }
        })
        .catch(function (err) {
          nextBtn.disabled = false;
          nextBtn.style.opacity = "";
          renderErrors({ general: "Network error. Please try again." });
          console.error(err);
        });
    });
  }

  if (backBtn) {
    backBtn.addEventListener("click", function () {
      if (currentStep > 1) {
        showStep(currentStep - 1);
        clearErrors();
      }
    });
  }

  /* ---- Completed-step click to navigate back (safe: already validated) ---- */
  var stepper = document.getElementById("student-stepper");
  if (stepper) {
    stepper.addEventListener("click", function (e) {
      var item = e.target.closest(".sp-step");
      if (!item) return;
      var s = Number(item.dataset.step);
      if (s < currentStep && s >= 1) {
        showStep(s);
        clearErrors();
      }
    });
  }

  if (submitBtn) {
    submitBtn.addEventListener("click", function () {
      if (submitted) return;
      clearErrors();
      if (!validateCurrentStep()) return;

      submitted = true;
      submitBtn.disabled = true;
      submitBtn.classList.add("busy");

      var fd = appendHiddenRole(new FormData(form));

      fetch(form.action, {
        method: "POST",
        body: fd,
        headers: { "X-Requested-With": "XMLHttpRequest" }
      })
        .then(function (r) { return r.json(); })
        .then(function (data) {
          submitted = false;
          submitBtn.disabled = false;
          submitBtn.classList.remove("busy");
          if (data && data.success) {
            if (data.redirect) {
              window.location.href = data.redirect;
              return;
            }
            var ok = document.createElement("div");
            ok.className = "sp-error success";
            ok.textContent = data.message || "Account created successfully.";
            errorContainer.appendChild(ok);
            /* soft success highlight pulse */
            if (ok) ok.style.boxShadow = "0 0 0 4px " + getComputedStyle(document.documentElement).getPropertyValue("--sp-success-bg");
          } else if (data && data.errors) {
            renderErrors(data.errors);
          } else if (data && data.message) {
            renderErrors({ general: data.message });
          }
        })
        .catch(function (err) {
          submitted = false;
          submitBtn.disabled = false;
          submitBtn.classList.remove("busy");
          renderErrors({ general: "Network error. Please check your connection and try again." });
          console.error(err);
        });
    });
  }

  /* ---------- Auto-clear field errors on interaction ---------- */
  function clearFieldError() {
    this.classList.remove("has-error");
    var spans = form.querySelectorAll('[data-field="' + this.name + '"].sp-field-error');
    spans.forEach(function (el) { el.remove(); });
  }
  form.querySelectorAll("input, select, textarea").forEach(function (input) {
    input.addEventListener("input", clearFieldError);
    input.addEventListener("change", clearFieldError);
  });

  /* ---------- Password interactions ---------- */
  function updateReq(id, valid) {
    var el = document.getElementById(id);
    if (el) {
      el.classList.toggle("valid", valid);
    }
  }

  function updateStrength(pwd) {
    var hasLetter = /[A-Za-z]/.test(pwd);
    var hasNumber = /[0-9]/.test(pwd);
    var hasSpecial = /[^A-Za-z0-9]/.test(pwd);
    var lengthOk = pwd.length >= 8;
    var score = 0;
    if (lengthOk) score++;
    if (hasLetter) score++;
    if (hasNumber) score++;
    if (hasSpecial) score++;

    var labels = ["", "Weak", "Fair", "Good", "Strong"];
    var fill = document.getElementById("pw-strength-fill");
    var label = document.getElementById("pw-strength-label");
    if (!pwd) {
      if (fill) { fill.className = "sp-pw-fill"; }
      if (label) label.textContent = "";
    } else {
      if (fill) fill.className = "sp-pw-fill score-" + score;
      if (label) label.textContent = labels[score];
    }
  }

  function updateMatchState() {
    if (!passwordInput || !confirmInput) return;
    var pwd = passwordInput.value;
    var confirm = confirmInput.value;
    var mismatch = document.getElementById("pw-mismatch");
    var match = document.getElementById("pw-match");
    if (!confirm) {
      if (mismatch) mismatch.classList.remove("visible");
      if (match) match.classList.remove("visible");
      return;
    }
    if (pwd !== confirm) {
      if (mismatch) mismatch.classList.add("visible");
      if (match) match.classList.remove("visible");
    } else {
      if (mismatch) mismatch.classList.remove("visible");
      if (match) match.classList.add("visible");
    }
  }

  if (passwordInput) {
    passwordInput.addEventListener("input", function () {
      var pwd = this.value;
      updateReq("req-length", pwd.length >= 8);
      updateReq("req-letter", /[A-Za-z]/.test(pwd));
      updateReq("req-number", /[0-9]/.test(pwd));
      updateReq("req-special", /[^A-Za-z0-9]/.test(pwd));
      updateStrength(pwd);
      updateMatchState();
    });
  }
  if (confirmInput) {
    confirmInput.addEventListener("input", updateMatchState);
  }

  /* Password visibility toggles */
  function initPasswordToggle(toggle) {
    var target = document.getElementById(toggle.getAttribute("data-target"));
    if (!target) return;
    var openIcon = toggle.querySelector(".sp-eye-open");
    var closedIcon = toggle.querySelector(".sp-eye-closed");
    toggle.addEventListener("click", function () {
      var isPwd = target.type === "password";
      target.type = isPwd ? "text" : "password";
      toggle.setAttribute("aria-pressed", isPwd ? "true" : "false");
      toggle.setAttribute("aria-label", isPwd ? "Hide password" : "Show password");
      if (openIcon) openIcon.style.display = isPwd ? "none" : "block";
      if (closedIcon) closedIcon.style.display = isPwd ? "block" : "none";
      target.focus({ preventScroll: true });
    });
  }
  document.querySelectorAll(".sp-pw-toggle").forEach(initPasswordToggle);

  /* ---------- Photo uploader interactions ---------- */
  function readFilePreview(file) {
    if (!file || !file.type || !file.type.startsWith("image/")) return;
    if (file.size > 2 * 1024 * 1024) {
      renderErrors({ profile_photo: "Photo must be smaller than 2 MB." });
      return;
    }
    var url = URL.createObjectURL(file);
    if (photoPreview) {
      photoPreview.src = url;
      photoPreview.onload = function () { URL.revokeObjectURL(url); };
    }
    if (photoArea) photoArea.classList.add("has-preview");
  }

  function resetPhoto() {
    if (photoInput) photoInput.value = "";
    if (photoPreview) { photoPreview.src = ""; }
    if (photoArea) photoArea.classList.remove("has-preview");
  }

  if (photoInput) {
    photoInput.addEventListener("change", function () {
      var file = this.files && this.files[0];
      if (file) readFilePreview(file);
    });
  }

  if (photoRemove) {
    photoRemove.addEventListener("click", function () {
      resetPhoto();
      var span = form.querySelector('[data-field="profile_photo"].sp-field-error');
      if (span) span.remove();
      if (photoArea && photoArea.classList) photoArea.classList.remove("has-error");
    });
  }

  /* Drag & drop polish */
  if (photoArea && photoInput) {
    ["dragenter", "dragover"].forEach(function (ev) {
      photoArea.addEventListener(ev, function (e) {
        e.preventDefault();
        e.stopPropagation();
        photoArea.classList.add("dragover");
      });
    });
    ["dragleave", "drop"].forEach(function (ev) {
      photoArea.addEventListener(ev, function (e) {
        e.preventDefault();
        e.stopPropagation();
        photoArea.classList.remove("dragover");
      });
    });
    photoArea.addEventListener("drop", function (e) {
      var file = e.dataTransfer.files && e.dataTransfer.files[0];
      if (file) {
        var dt = new DataTransfer();
        dt.items.add(file);
        photoInput.files = dt.files;
        readFilePreview(file);
      }
    });
  }

  /* ---------- Initialise ---------- */
  showStep(1);
})();
