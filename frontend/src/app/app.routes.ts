import { Routes } from '@angular/router';

import { BuildRagIndexComponent } from './build-rag-index/build-rag-index.component';
import { ChatComponent } from './chat/chat.component';

export const appRoutes: Routes = [
  { path: '', component: ChatComponent },
  { path: 'build-rag', component: BuildRagIndexComponent },
  { path: '**', redirectTo: '' },
];
