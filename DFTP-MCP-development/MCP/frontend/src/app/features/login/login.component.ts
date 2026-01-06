import { Component, inject, signal } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login',
  standalone: true,
  imports: [CommonModule, FormsModule],
  template: `
    <div class="login-container">
      <div class="login-card">
        <h2>🔐 Welcome Back</h2>
        <p class="subtitle">Please login to access the Orchestrator</p>
        
        <div class="form-group">
          <label>Username</label>
          <input type="text" [(ngModel)]="username" placeholder="Enter username" />
        </div>
        
        <div class="form-group">
          <label>Password</label>
          <input type="password" [(ngModel)]="password" placeholder="Enter password" />
        </div>

        <div *ngIf="error()" class="error-message">
          {{ error() }}
        </div>

        <button (click)="onLogin()" [disabled]="isLoading()">
          {{ isLoading() ? 'Logging in...' : 'Login' }}
        </button>
      </div>
    </div>
  `,
  styles: [`
    .login-container {
      display: flex;
      justify-content: center;
      align-items: center;
      height: 100vh;
      background: linear-gradient(135deg, var(--sidebar-bg-from) 0%, var(--sidebar-bg-to) 100%);
    }
    .login-card {
      background: white;
      padding: 2.5rem;
      border-radius: 12px;
      box-shadow: 0 4px 20px rgba(0,0,0,0.2);
      width: 100%;
      max-width: 400px;
      border-top: 4px solid var(--primary-color);
    }
    h2 { margin: 0 0 0.5rem 0; color: var(--sidebar-bg-from); }
    .subtitle { color: #666; margin-bottom: 2rem; font-size: 0.9rem; }
    .form-group { margin-bottom: 1.5rem; }
    label { display: block; margin-bottom: 0.5rem; font-weight: 500; color: #444; }
    input {
      width: 100%;
      padding: 0.75rem;
      border: 1px solid #ddd;
      border-radius: 6px;
      font-size: 1rem;
      transition: all 0.2s;
      background-color: #f8f9fa;
    }
    input:focus { 
      border-color: var(--primary-color); 
      outline: none; 
      box-shadow: 0 0 0 2px rgba(0, 198, 162, 0.2);
    }
    button {
      width: 100%;
      padding: 0.75rem;
      background-color: var(--primary-color);
      color: var(--sidebar-bg-from);
      border: none;
      border-radius: 6px;
      font-size: 1rem;
      font-weight: 600;
      cursor: pointer;
      transition: all 0.2s;
      box-shadow: 0 4px 6px rgba(0, 198, 162, 0.3);
    }
    button:hover:not(:disabled) {
      background-color: var(--accent-color);
      box-shadow: 0 4px 12px rgba(79, 255, 225, 0.4);
    }
    button:disabled { opacity: 0.7; cursor: not-allowed; }
    .error-message {
      color: #721c24;
      font-size: 0.875rem;
      margin-bottom: 1rem;
      padding: 0.75rem;
      background-color: #f8d7da;
      border-left: 4px solid #f5c6cb;
      border-radius: 4px;
    }
  `]
})
export class LoginComponent {
  authService = inject(AuthService);

  username = '';
  password = '';
  isLoading = signal(false);
  error = signal('');

  onLogin() {
    if (!this.username || !this.password) {
      this.error.set('Please fill in all fields');
      return;
    }

    this.isLoading.set(true);
    this.error.set('');
    this.authService.login({ username: this.username, password: this.password })
      .subscribe({
        next: (res) => {
          console.log("Login SUCCESS:", res);
        
        },
        error: (err) => {
          console.error("Login ERROR:", err);
          this.error.set('Login failed. Please check credentials.');
          this.isLoading.set(false);
        },
        complete: () => {
          console.log("Login observable completed");
          this.isLoading.set(false);
        }
      });
  }
}
