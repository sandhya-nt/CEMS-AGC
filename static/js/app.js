document.addEventListener("DOMContentLoaded", () => {
  document.querySelectorAll(".flash").forEach((el) => {
    setTimeout(() => { if (el) el.style.opacity = "0"; }, 5000);
  });
});
