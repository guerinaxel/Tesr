import { CommonModule } from '@angular/common';
import { HttpClient } from '@angular/common/http';
import { Component, OnDestroy, inject } from '@angular/core';
import { FormsModule } from '@angular/forms';

import { environment } from '../../environments/environment';

type ToastType = 'success' | 'error';

interface ToastState {
  message: string;
  type: ToastType;
}

@Component({
  selector: 'app-build-rag-index',
  standalone: true,
  imports: [CommonModule, FormsModule],
  templateUrl: './build-rag-index.component.html',
  styleUrls: ['./build-rag-index.component.scss'],
})
export class BuildRagIndexComponent implements OnDestroy {
  private readonly http = inject(HttpClient);

  root = '';
  isSubmitting = false;
  toast: ToastState | null = null;

  private toastTimer?: ReturnType<typeof setTimeout>;

  onSubmit(): void {
    if (this.isSubmitting) {
      return;
    }

    this.isSubmitting = true;

    const payload = { root: this.root.trim() || null };

    this.http
      .post(`${environment.apiUrl}/code-qa/build-rag/`, payload)
      .subscribe({
        next: () => {
          this.isSubmitting = false;
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
