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
export class AuthService {
    private apiUrl = 'http://localhost:8081/api';;
    private tokenSignal = signal<any | null>(this.loadToken());
    isAuthenticated = computed(() => !!this.tokenSignal());
    currentUserScope = computed(() => {
        const token = this.tokenSignal()?.access_token;
        if (!token) {
            return 'General';
        }

        try {
            const decoded = jwtDecode<JwtPayload>(token);
            const scope = decoded.scope?.split(' ').find(s => s !== 'openid') || 'General';
            return scope;
        } catch (err) {
            console.error("Error decoding token:", err);
            return 'General';
        }
    });

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
        const tokens = this.tokenSignal();
        const idToken = tokens?.id_token;

        localStorage.removeItem('auth_tokens');
        this.tokenSignal.set(null);

        const keycloakUrl = 'http://localhost:8180';
        const realm = 'authentication';
        const redirectUri = 'http://localhost:4200/login-callback';

        // We use the backend callback as the redirect URI because it is whitelisted in Keycloak.
        // The backend will then redirect us to /login.
        const gatewayCallback = 'http://localhost:8081/api/auth/callback';

        let logoutUrl = `${keycloakUrl}/realms/${realm}/protocol/openid-connect/logout?post_logout_redirect_uri=${encodeURIComponent(gatewayCallback)}`;

        const isValidIdToken = (token: any) => typeof token === 'string' && token.length > 20 && token !== 'null' && token !== 'undefined';

        if (isValidIdToken(idToken)) {
            logoutUrl += `&id_token_hint=${encodeURIComponent(idToken)}`;
            window.location.href = logoutUrl;
        } else {
            alert('Logout incomplete: Backend not updated? Clearing local session only.');
            window.location.href = '/';
        }
    }

    getToken(): any {
        return this.tokenSignal();
    }

    private setToken(tokens: any) {
        localStorage.setItem('auth_tokens', JSON.stringify(tokens));
        this.tokenSignal.set(tokens);
    }


    setTokenPublic(tokens: any) {
        this.setToken(tokens);
    }

    private loadToken(): any | null {
        const stored = localStorage.getItem('auth_tokens');
        return stored ? JSON.parse(stored) : null;
    }
}
