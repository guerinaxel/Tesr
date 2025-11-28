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
    // Arrange
    service
      .sendQuestion({ question: 'Test', system_prompt: 'code expert', topic_id: 1 })
      .subscribe();

    // Act
    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/`);

    // Assert
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      question: 'Test',
      system_prompt: 'code expert',
      topic_id: 1,
    });
    req.flush({ answer: 'ok' });
  });

  it('fetches the list of topics', () => {
    // Arrange & Act
    service.getTopics().subscribe();

    // Assert
    const req = httpMock.expectOne(`${environment.apiUrl}/topics/`);
    expect(req.request.method).toBe('GET');
    req.flush({ topics: [], next_offset: null });
  });

  it('applies pagination params when provided', () => {
    // Arrange & Act
    service.getTopics({ limit: 15 }).subscribe();

    // Assert
    const req = httpMock.expectOne(`${environment.apiUrl}/topics/?limit=15`);
    expect(req.request.method).toBe('GET');
    req.flush({ topics: [], next_offset: null });
  });

  it('fetches topic details', () => {
    // Arrange & Act
    service.getTopicDetail(3, { offset: 20, limit: 10 }).subscribe();

    // Assert
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
    // Arrange & Act
    service.createTopic('New Feature').subscribe();

    // Assert
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

  it('searches across topics, questions, and answers with pagination', () => {
    // Arrange & Act
    service.searchEverything('term', {
      limit: 5,
      topics_offset: 10,
      questions_offset: 20,
      answers_offset: 30,
    }).subscribe();

    // Assert
    const req = httpMock.expectOne(
      `${environment.apiUrl}/search/?q=term&limit=5&topics_offset=10&questions_offset=20&answers_offset=30`
    );
    expect(req.request.method).toBe('GET');
    req.flush({
      topics: { items: [], next_offset: null },
      questions: { items: [], next_offset: null },
      answers: { items: [], next_offset: null },
    });
  });

  it('searches without optional offsets', () => {
    // Arrange & Act
    service.searchEverything('quick').subscribe();

    // Assert
    const req = httpMock.expectOne(`${environment.apiUrl}/search/?q=quick`);
    expect(req.request.method).toBe('GET');
    req.flush({
      topics: { items: [], next_offset: null },
      questions: { items: [], next_offset: null },
      answers: { items: [], next_offset: null },
    });
  });

  it('applies an offset without a limit when fetching topics', () => {
    // Arrange & Act
    service.getTopics({ offset: 30 }).subscribe();

    // Assert
    const req = httpMock.expectOne(`${environment.apiUrl}/topics/?offset=30`);
    expect(req.request.method).toBe('GET');
    req.flush({ topics: [], next_offset: null });
  });
});
