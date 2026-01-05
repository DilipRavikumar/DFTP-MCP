import { Component } from '@angular/core';
import { Router } from '@angular/router';

@Component({
  selector: 'app-dashboard',
  template: `
    <div class="flex justify-center items-center h-screen">
      <button (click)="login()" class="px-6 py-3 bg-blue-600 text-white rounded-lg">
        Login
      </button>
    </div>
  `
})
export class DashboardComponent {
  constructor(private router: Router) {}
login() {
  window.location.href = 'http://localhost:8081/api/auth/login?redirect_uri=http://localhost:4200/login-callback';
}

}
