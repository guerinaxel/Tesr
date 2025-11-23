import { inject, Injectable } from '@angular/core';
import { HttpClient } from '@angular/common/http';

import { environment } from '../../environments/environment';

export interface TopicSummary {
  id: number;
  name: string;
  message_count: number;
}

export interface TopicDetail extends TopicSummary {
  messages: Array<{ role: 'user' | 'assistant'; content: string }>;
}

export interface CodeQaPayload extends Record<string, string> {
  question: string;
  system_prompt: string;
  topic_id?: string;
  custom_prompt?: string;
}

export interface CodeQaResponse {
  answer: string;
  meta?: unknown;
}

@Injectable({ providedIn: 'root' })
export class ChatDataService {
  private readonly http = inject(HttpClient);
  private readonly apiUrl = environment.apiUrl;

  sendQuestion(payload: CodeQaPayload) {
    return this.http.post<CodeQaResponse>(`${this.apiUrl}/code-qa/`, payload);
  }

  getTopics() {
    return this.http.get<{ topics: TopicSummary[] }>(`${this.apiUrl}/topics/`);
  }

  getTopicDetail(topicId: number) {
    return this.http.get<TopicDetail>(`${this.apiUrl}/topics/${topicId}/`);
  }

  createTopic(name: string) {
    return this.http.post<TopicDetail>(`${this.apiUrl}/topics/`, { name });
  }
}
