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
import { MatProgressBarModule } from '@angular/material/progress-bar';

import { environment } from '../../environments/environment';

type ToastType = 'success' | 'error';

type BuildStatus = 'idle' | 'running' | 'completed' | 'error';

interface BuildProgress {
  status: BuildStatus;
  percent: number;
  message: string;
  root: string | null;
}

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
    MatProgressBarModule,
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
  progress: BuildProgress | null = null;
  readonly pollIntervalMs = 1500;

  private toastTimer?: ReturnType<typeof setTimeout>;
  private pollTimer?: ReturnType<typeof setInterval>;

  ngOnInit(): void {
    this.fetchState();
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
      .post<{ detail: string; root: string | null; progress: BuildProgress }>(`${environment.apiUrl}/code-qa/build-rag/`, payload)
      .subscribe({
        next: (response) => {
          this.isSubmitting = false;
          const usedRoot = response.root ?? trimmedRoot ?? null;
          if (usedRoot) {
            this.lastUsedRoot = usedRoot;
            this.root = usedRoot;
          }
          this.applyProgress(response.progress);
          this.showToast('RAG index build triggered.', 'success');
        },
        error: (err) => {
          this.isSubmitting = false;
          const message =
            err?.error?.detail ?? 'Failed to trigger the RAG index build.';
          if (err?.error?.progress) {
            this.applyProgress(err.error.progress);
          }
          this.showToast(message, 'error');
        },
      });
  }

  ngOnDestroy(): void {
    this.stopProgressPolling();
    this.clearToastTimer();
  }

  private fetchState(): void {
    this.isLoadingRoot = true;
    this.http
      .get<{ root: string | null; progress: BuildProgress }>(`${environment.apiUrl}/code-qa/build-rag/`)
      .subscribe({
        next: ({ root, progress }) => {
          if (root) {
            this.root = root;
            this.lastUsedRoot = root;
          }
          this.applyProgress(progress);
        },
        error: () => {
          this.showToast('Impossible de récupérer le dernier chemin utilisé.', 'error');
        },
        complete: () => {
          this.isLoadingRoot = false;
        },
      });
  }

  private refreshProgress(): void {
    this.http
      .get<{ progress: BuildProgress }>(`${environment.apiUrl}/code-qa/build-rag/`)
      .subscribe({
        next: ({ progress }) => this.applyProgress(progress),
        error: () => this.stopProgressPolling(),
      });
  }

  private applyProgress(progress: BuildProgress | null): void {
    this.progress = progress;
    if (progress?.status === 'running') {
      this.startProgressPolling();
    } else {
      this.stopProgressPolling();
    }
  }

  private startProgressPolling(): void {
    if (this.pollTimer) {
      return;
    }

    this.pollTimer = setInterval(() => this.refreshProgress(), this.pollIntervalMs);
  }

  private stopProgressPolling(): void {
    if (this.pollTimer) {
      clearInterval(this.pollTimer);
      this.pollTimer = undefined;
    }
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
