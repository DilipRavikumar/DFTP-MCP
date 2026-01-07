import { Injectable, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';
import { jwtDecode } from 'jwt-decode';

interface JwtPayload {
    scope?: string;
}

@Injectable({
    providedIn: 'root'
})

@Injectable({ providedIn: 'root' })
export class AuthService {
  private apiUrl = 'http://localhost:8081/api';
  isAuthenticated = signal(false);
  currentUserScope = signal<string>('General');
  constructor(private http: HttpClient, private router: Router) {}

  login() {
    window.location.href = `${this.apiUrl}/auth/login`;
  }

logout() {
     this.isAuthenticated.set(false);
  window.location.href = `${this.apiUrl}/auth/logout`;
}





 me() {
    return this.http.get<any>(`${this.apiUrl}/auth/me`, {
      withCredentials: true
    });
  }

  fetchUser() {
  this.me().subscribe({
    next: (res) => {
      this.isAuthenticated.set(res.authenticated);
      this.currentUserScope.set(res.scope); // ✅ Here we update with actual scope from token
    },
    error: () => {
      this.isAuthenticated.set(false);
      this.currentUserScope.set('General'); // fallback if token missing or invalid
    }
  });
}

}
