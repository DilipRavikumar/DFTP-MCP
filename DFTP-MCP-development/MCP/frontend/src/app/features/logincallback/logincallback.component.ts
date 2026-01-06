import { Component, OnInit, inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login-callback',
  template: `<p>Logging in...</p>`
})
export class LoginCallbackComponent implements OnInit {
  private authService = inject(AuthService);
  constructor(private router: Router) { }

  ngOnInit() {
    const params = new URLSearchParams(window.location.search);
    const token = params.get('token');
    const idToken = params.get('id_token');

    if (token) {
      // Store as an object with access_token property to match AuthService expectations
      this.authService.setTokenPublic({
        access_token: token,
        id_token: idToken
      });
      this.router.navigate(['/chat']);
    } else {
      // If no token, we might be returning from logout
      this.router.navigate(['/']);
    }
  }
}
