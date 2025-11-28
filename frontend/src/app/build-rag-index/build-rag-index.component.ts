import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnDestroy, OnInit, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';
import { MatButtonModule } from '@angular/material/button';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatIconModule } from '@angular/material/icon';
import { MatInputModule } from '@angular/material/input';
import { MatProgressSpinnerModule } from '@angular/material/progress-spinner';

import { environment } from '../../environments/environment';

type ToastType = 'success' | 'error';

interface ToastState {
  message: string;
  type: ToastType;
}

@Component({
  selector: 'app-build-rag-index',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    MatButtonModule,
    MatCardModule,
    MatFormFieldModule,
    MatIconModule,
    MatInputModule,
    MatProgressSpinnerModule,
  ],
  templateUrl: './build-rag-index.component.html',
  styleUrls: ['./build-rag-index.component.scss'],
})
export class BuildRagIndexComponent implements OnInit, OnDestroy {
  private readonly http = inject(HttpClient);

  root = '';
  lastUsedRoot: string | null = null;
  isSubmitting = false;
  isLoadingRoot = false;
  toast: ToastState | null = null;

  private toastTimer?: ReturnType<typeof setTimeout>;

  ngOnInit(): void {
    this.isLoadingRoot = true;
    this.http.get<{ root: string | null }>(`${environment.apiUrl}/code-qa/build-rag/`).subscribe({
      next: ({ root }) => {
        if (root) {
          this.root = root;
          this.lastUsedRoot = root;
        }
      },
      error: () => {
        this.showToast('Impossible de récupérer le dernier chemin utilisé.', 'error');
        this.isLoadingRoot = false;
      },
      complete: () => {
        this.isLoadingRoot = false;
      },
    });
  }

  onSubmit(): void {
    this.triggerBuild(this.root);
  }

  onRebuild(): void {
    const fallbackRoot = this.lastUsedRoot ?? this.root;
    this.root = fallbackRoot;
    this.triggerBuild(fallbackRoot);
  }

  private triggerBuild(rootValue: string): void {
    if (this.isSubmitting) {
      return;
    }

    this.isSubmitting = true;

    const trimmedRoot = rootValue?.trim();
    const payload = { root: trimmedRoot || null };

    this.http
      .post<{ detail: string; root: string | null }>(`${environment.apiUrl}/code-qa/build-rag/`, payload)
      .subscribe({
        next: (response) => {
          this.isSubmitting = false;
          const usedRoot = response.root ?? trimmedRoot ?? null;
          if (usedRoot) {
            this.lastUsedRoot = usedRoot;
            this.root = usedRoot;
          }
          this.showToast('RAG index build triggered.', 'success');
        },
        error: (err) => {
          this.isSubmitting = false;
          const message =
            err?.error?.detail ?? 'Failed to trigger the RAG index build.';
          this.showToast(message, 'error');
        },
      });
  }

  ngOnDestroy(): void {
    this.clearToastTimer();
  }

  private showToast(message: string, type: ToastType): void {
    this.toast = { message, type };
    this.clearToastTimer();
    this.toastTimer = setTimeout(() => {
      this.toast = null;
    }, 4000);
  }

  private clearToastTimer(): void {
    if (this.toastTimer) {
      clearTimeout(this.toastTimer);
      this.toastTimer = undefined;
    }
  }
}
