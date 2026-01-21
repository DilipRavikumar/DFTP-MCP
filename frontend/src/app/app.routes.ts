import { Routes } from '@angular/router';
import { authGuard } from './core/auth.guard';
import { DashboardComponent } from './features/dashboard/dashboard.component';
import { LoginCallbackComponent } from './features/logincallback/logincallback.component';
import { ChatComponent } from './features/chat/chat.component';

// export const routes: Routes = [
//     {
//         path: '', component: DashboardComponent
//     },
//     {
//         path: 'login',
//         loadComponent: () => import('./features/login/login.component').then(m => m.LoginComponent)
//     },
//     {
//         path: 'chat',
//         loadComponent: () => import('./features/chat/chat.component').then(m => m.ChatComponent),
//         canActivate: [authGuard]
//     }
// ];

export const routes = [
  { path: '', component: DashboardComponent
   },

  { path: 'login-callback', component: LoginCallbackComponent },
  { path: 'chat', component: ChatComponent,
        canActivate: [authGuard]
   }
];
