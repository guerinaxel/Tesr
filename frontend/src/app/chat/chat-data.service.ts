import { inject, Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';

import { environment } from '../../environments/environment';

export interface TopicSummary {
  id: number;
  name: string;
  message_count: number;
}

export interface TopicDetail extends TopicSummary {
  messages: Array<{ role: 'user' | 'assistant'; content: string }>;
  next_offset: number | null;
}

export interface PaginatedTopicList {
  topics: TopicSummary[];
  next_offset: number | null;
}

export interface SearchCategory<T> {
  items: T[];
  next_offset: number | null;
}

export type SearchTopicResult = TopicSummary;

export interface SearchMessageResult {
  id: number;
  topic_id: number;
  topic_name: string;
  content: string;
}

export interface SearchResponse {
  topics: SearchCategory<SearchTopicResult>;
  questions: SearchCategory<SearchMessageResult>;
  answers: SearchCategory<SearchMessageResult>;
}

export interface CodeQaPayload extends Record<string, string | number | undefined> {
  question: string;
  system_prompt: string;
  topic_id?: number;
  custom_prompt?: string;
}

export interface CodeQaResponse {
  answer: string;
  meta?: unknown;
}

export interface PaginationOptions {
  offset?: number;
  limit?: number;
}

@Injectable({ providedIn: 'root' })
export class ChatDataService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  sendQuestion(payload: CodeQaPayload) {
    return this.http.post<CodeQaResponse>(`${this.apiUrl}/code-qa/`, payload);
  }

  getTopics(options: PaginationOptions = {}) {
    const params = new HttpParams({ fromObject: this.buildPaginationParams(options) });

    return this.http.get<PaginatedTopicList>(`${this.apiUrl}/topics/`, { params });
  }

  getTopicDetail(topicId: number, options: PaginationOptions = {}) {
    const params = new HttpParams({ fromObject: this.buildPaginationParams(options) });

    return this.http.get<TopicDetail>(`${this.apiUrl}/topics/${topicId}/`, { params });
  }

  createTopic(name: string) {
    return this.http.post<TopicDetail>(`${this.apiUrl}/topics/`, { name });
  }

  searchEverything(query: string, options: Record<string, number> = {}) {
    const params = new HttpParams({
      fromObject: {
        q: query,
        limit: options.limit != null ? String(options.limit) : undefined,
        topics_offset:
          options.topics_offset != null ? String(options.topics_offset) : undefined,
        questions_offset:
          options.questions_offset != null
            ? String(options.questions_offset)
            : undefined,
        answers_offset:
          options.answers_offset != null ? String(options.answers_offset) : undefined,
      },
    });

    return this.http.get<SearchResponse>(`${this.apiUrl}/search/`, { params });
  }

  private buildPaginationParams(options: PaginationOptions): Record<string, string> {
    const params: Record<string, string> = {};
    if (options.offset != null) {
      params['offset'] = String(options.offset);
    }
    if (options.limit != null) {
      params['limit'] = String(options.limit);
    }
    return params;
  }
}
