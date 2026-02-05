import { bootstrapApplication } from '@angular/platform-browser';
import { appConfig } from './app/app.config';
import { AppComponent } from './app/app.component';

// Polyfill for crypto.randomUUID in insecure contexts (HTTP)
if (typeof crypto !== 'undefined' && !crypto.randomUUID) {
    // @ts-ignore
    crypto.randomUUID = () => {
        return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function (c) {
            var r = Math.random() * 16 | 0, v = c === 'x' ? r : (r & 0x3 | 0x8);
            return v.toString(16);
        }) as any;
    };
}


bootstrapApplication(AppComponent, appConfig)
    .catch((err) => console.error(err));
