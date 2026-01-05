import { Injectable, computed, signal } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { Router } from '@angular/router';
import { Observable, tap } from 'rxjs';

@Injectable({
    providedIn: 'root'
})
export class AuthService {
    private apiUrl = 'http://localhost:8081/api';;

    private tokenSignal = signal<any | null>(this.loadToken());
    isAuthenticated = computed(() => !!this.tokenSignal());
    currentUserScope = computed(() => this.tokenSignal()?.scope || 'General');

    constructor(private http: HttpClient, private router: Router) { }

    login(credentials: { username: string, password: string }) {
  return this.http.post(`${this.apiUrl}/login`, credentials)
    .pipe(tap((res: any) => {
      if (res.access_token) {
        this.setToken(res);
      }
    }));
}

    logout() {
        localStorage.removeItem('auth_tokens');
        this.tokenSignal.set(null);
        this.router.navigate(['/login']);
    }

    getToken(): any {
        return this.tokenSignal();
    }

    private setToken(tokens: any) {
        localStorage.setItem('auth_tokens', JSON.stringify(tokens));
        this.tokenSignal.set(tokens);
    }

    private loadToken(): any | null {
        const stored = localStorage.getItem('auth_tokens');
        return stored ? JSON.parse(stored) : null;
    }
}
