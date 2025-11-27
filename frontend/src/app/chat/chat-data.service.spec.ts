import { TestBed } from '@angular/core/testing';
import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';

import { environment } from '../../environments/environment';
import { ChatDataService } from './chat-data.service';

describe('ChatDataService', () => {
  let service: ChatDataService;
  let httpMock: HttpTestingController;

  beforeEach(() => {
    TestBed.configureTestingModule({
      imports: [HttpClientTestingModule],
    });

    service = TestBed.inject(ChatDataService);
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('sends a question payload to the code-qa endpoint', () => {
    service
      .sendQuestion({ question: 'Test', system_prompt: 'code expert', topic_id: 1 })
      .subscribe();

    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      question: 'Test',
      system_prompt: 'code expert',
      topic_id: 1,
    });
    req.flush({ answer: 'ok' });
  });

  it('fetches the list of topics', () => {
    service.getTopics().subscribe();

    const req = httpMock.expectOne(`${environment.apiUrl}/topics/`);
    expect(req.request.method).toBe('GET');
    req.flush({ topics: [], next_offset: null });
  });

  it('applies pagination params when provided', () => {
    service.getTopics({ limit: 15 }).subscribe();

    const req = httpMock.expectOne(`${environment.apiUrl}/topics/?limit=15`);
    expect(req.request.method).toBe('GET');
    req.flush({ topics: [], next_offset: null });
  });

  it('fetches topic details', () => {
    service.getTopicDetail(3, { offset: 20, limit: 10 }).subscribe();

    const req = httpMock.expectOne(
      `${environment.apiUrl}/topics/3/?offset=20&limit=10`
    );
    expect(req.request.method).toBe('GET');
    req.flush({
      id: 3,
      name: 'Topic',
      message_count: 2,
      messages: [],
      next_offset: null,
    });
  });

  it('creates a new topic', () => {
    service.createTopic('New Feature').subscribe();

    const req = httpMock.expectOne(`${environment.apiUrl}/topics/`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ name: 'New Feature' });
    req.flush({
      id: 10,
      name: 'New Feature',
      message_count: 0,
      messages: [],
      next_offset: null,
    });
  });
});
