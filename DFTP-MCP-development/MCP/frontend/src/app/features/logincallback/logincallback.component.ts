import { Component, OnInit, inject } from '@angular/core';
import { Router } from '@angular/router';
import { AuthService } from '../../core/services/auth.service';

@Component({
  selector: 'app-login-callback',
  template: `<p>Logging in...</p>`
})
export class LoginCallbackComponent implements OnInit {
  private authService = inject(AuthService);
  constructor(private router: Router) {}

  ngOnInit() {  
    const token = new URLSearchParams(window.location.search).get('token');
    if (token) {
      // Store as an object with access_token property to match AuthService expectations
      this.authService.setTokenPublic({ access_token: token });
      this.router.navigate(['/chat']);
    } else {
      console.error("No token in callback");
      
    }
  }
}
