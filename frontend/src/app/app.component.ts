import { Component, OnInit, computed, inject, model, signal } from '@angular/core';
import { RouterLink, RouterLinkActive, RouterOutlet } from '@angular/router';
import { MatButtonModule } from '@angular/material/button';
import { MatIconModule } from '@angular/material/icon';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { Subject } from 'rxjs';
import { debounceTime, distinctUntilChanged } from 'rxjs/operators';
import { takeUntilDestroyed } from '@angular/core/rxjs-interop';
import { ChatDataService, SearchResponse } from './chat/chat-data.service';

type SearchOffsets = { topics: number; questions: number; answers: number };

@Component({
  selector: 'app-root',
  standalone: true,
  imports: [
    CommonModule,
    FormsModule,
    RouterOutlet,
    RouterLink,
    RouterLinkActive,
    MatToolbarModule,
    MatButtonModule,
    MatIconModule,
    MatFormFieldModule,
    MatInputModule,
  ],
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
})
export class AppComponent implements OnInit {
  private readonly chatDataService = inject(ChatDataService);

  readonly globalSearchQuery = model('');
  readonly globalSearchResults = signal<SearchResponse | null>(null);
  readonly globalSearchLoading = signal(false);
  readonly searchOffsets = signal<SearchOffsets>({ topics: 0, questions: 0, answers: 0 });
  readonly hasSearchResults = computed(() => {
    const results = this.globalSearchResults();
    if (!results) return false;
    return (
      (results.topics.items?.length ?? 0) > 0 ||
      (results.questions.items?.length ?? 0) > 0 ||
      (results.answers.items?.length ?? 0) > 0
    );
  });
  readonly searchVisible = signal(false);

  private readonly search$ = new Subject<string>();

  ngOnInit(): void {
    this.search$
      .pipe(debounceTime(500), distinctUntilChanged(), takeUntilDestroyed())
      .subscribe((value) => this.runGlobalSearch(value));
  }

  onGlobalSearchChange(value: string): void {
    this.globalSearchQuery.set(value);
    this.searchOffsets.set({ topics: 0, questions: 0, answers: 0 });
    this.searchVisible.set(true);
    this.search$.next(value);
  }

  clearGlobalSearch(): void {
    this.globalSearchQuery.set('');
    this.globalSearchResults.set(null);
    this.searchOffsets.set({ topics: 0, questions: 0, answers: 0 });
    this.searchVisible.set(false);
  }

  loadMore(category: 'topics' | 'questions' | 'answers'): void {
    const results = this.globalSearchResults();
    const nextOffset = results?.[category]?.next_offset;
    if (nextOffset == null) return;

    const updatedOffsets = {
      ...this.searchOffsets(),
      [category]: nextOffset,
    } as SearchOffsets;
    this.searchOffsets.set(updatedOffsets);

    this.runGlobalSearch(this.globalSearchQuery(), updatedOffsets);
  }

  private runGlobalSearch(
    value: string,
    offsets: SearchOffsets = this.searchOffsets()
  ): void {
    const query = value.trim();
    if (!query) {
      this.globalSearchResults.set(null);
      this.globalSearchLoading.set(false);
      return;
    }

    this.globalSearchLoading.set(true);
    this.chatDataService
      .searchEverything(query, {
        limit: 5,
        topics_offset: offsets.topics,
        questions_offset: offsets.questions,
        answers_offset: offsets.answers,
      })
      .subscribe({
        next: (res) => {
          this.globalSearchResults.set(res);
          this.globalSearchLoading.set(false);
        },
        error: () => {
          this.globalSearchResults.set(null);
          this.globalSearchLoading.set(false);
        },
      });
  }
}
