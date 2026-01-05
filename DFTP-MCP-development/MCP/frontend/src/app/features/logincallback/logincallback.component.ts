import { Component, OnInit } from '@angular/core';
import { Router } from '@angular/router';

@Component({
  selector: 'app-login-callback',
  template: `<p>Logging in...</p>`
})
export class LoginCallbackComponent implements OnInit {
  constructor(private router: Router) {}

  ngOnInit() {
    const token = new URLSearchParams(window.location.search).get('token');

    if (token) {
      localStorage.setItem('token', token);
      this.router.navigate(['/chat']);
    }
  }
}
