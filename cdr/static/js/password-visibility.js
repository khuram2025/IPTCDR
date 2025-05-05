// Toggle password visibility for all password fields with .toggle-password
(function() {
  document.addEventListener('DOMContentLoaded', function() {
    document.querySelectorAll('.toggle-password').forEach(function(toggle) {
      toggle.addEventListener('click', function() {
        var input = document.getElementById(this.dataset.target);
        if (input.type === 'password') {
          input.type = 'text';
          this.classList.remove('fa-eye');
          this.classList.add('fa-eye-slash');
        } else {
          input.type = 'password';
          this.classList.remove('fa-eye-slash');
          this.classList.add('fa-eye');
        }
      });
    });
  });
})();
