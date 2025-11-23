import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';

import { environment } from '../../environments/environment';
import { ChatComponent } from './chat.component';


describe('ChatComponent', () => {
  let fixture: ComponentFixture<ChatComponent>;
  let component: ChatComponent;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ChatComponent, HttpClientTestingModule, NoopAnimationsModule],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);

    component.topics.set([{ id: 1, name: 'Default', message_count: 0 }]);
    component.selectedTopicId.set(1);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('sends a question to the backend and appends the assistant answer', fakeAsync(() => {
    component.question.set('Explain RAG');

    // Act
    component.onSubmit();
    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/`);
    req.flush({ answer: 'Contextual explanation' });
    const refreshReq = httpMock.expectOne(`${environment.apiUrl}/topics/1/`);
    refreshReq.flush({ id: 1, name: 'Default', message_count: 2, messages: [] });
    tick(200);

    // Assert
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({
      question: 'Explain RAG',
      system_prompt: 'code expert',
      topic_id: '1',
    });

    req.flush({ answer: 'Contextual explanation' });

    const refreshReq = httpMock.expectOne(`${environment.apiUrl}/topics/1/`);
    refreshReq.flush({ id: 1, name: 'Default', message_count: 2, messages: [] });

    expect(component.messages()[0]).toEqual(
      jasmine.objectContaining({ from: 'user', content: 'Explain RAG' })
    );
    expect(component.messages()[1]).toEqual(
      jasmine.objectContaining({ from: 'assistant', content: 'Contextual explanation' })
    );
    tick(200);
    expect(component.isSending()).toBeFalse();
  }));

  it('sends a custom prompt when selected', () => {
    component.question.set('Customise the system');
    component.systemPrompt.set('custom');
    component.customPrompt.set('You are concise');

    // Act
    component.onSubmit();
    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/`);
    req.flush({ answer: 'Acknowledged' });
    const refreshReq = httpMock.expectOne(`${environment.apiUrl}/topics/1/`);
    refreshReq.flush({ id: 1, name: 'Default', message_count: 2, messages: [] });

    // Assert
    expect(req.request.body).toEqual({
      question: 'Customise the system',
      system_prompt: 'custom',
      custom_prompt: 'You are concise',
      topic_id: '1',
    });
  });

  it('sends the message when pressing ctrl+space with content', () => {
    component.question.set('Quick send');

    // Act
    component.onSpaceSend(event);
    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/`);
    req.flush({ answer: 'Delivered' });
    const refreshReq = httpMock.expectOne(`${environment.apiUrl}/topics/1/`);
    refreshReq.flush({ id: 1, name: 'Default', message_count: 2, messages: [] });

    // Assert
    expect(component.messages()[0]).toEqual(
      jasmine.objectContaining({ from: 'user', content: 'Quick send' })
    );
    expect(component.messages()[1]).toEqual(
      jasmine.objectContaining({ from: 'assistant', content: 'Delivered' })
    );
  });

  it('does not send the message when pressing space without modifiers', () => {
    component.question.set('Should stay');
    const event = new KeyboardEvent('keydown', { key: ' ' });
    
    // Act
    component.onSpaceSend(event);

    // Assert
    httpMock.expectNone(`${environment.apiUrl}/code-qa/`);
    expect(component.messages().length).toBe(0);
    expect(component.isSending()).toBeFalse();
  });

  it('does not send when custom prompt is missing', () => {
    // Arrange
    component.question.set('Should block');
    component.systemPrompt.set('custom');
    component.customPrompt.set('   ');

    // Act
    component.onSubmit();

    // Assert
    httpMock.expectNone(`${environment.apiUrl}/code-qa/`);
    expect(component.messages().length).toBe(0);
    expect(component.isSending()).toBeFalse();
  });

  it('does not send a request for blank input', () => {
    // Arrange
    component.question.set('   ');

    // Act
    component.onSubmit();

    // Assert
    httpMock.expectNone(`${environment.apiUrl}/code-qa/`);
    expect(component.messages().length).toBe(0);
    expect(component.isSending()).toBeFalse();
  });

  it('shows an error message when the API call fails', fakeAsync(() => {
    // Arrange
    component.question.set('Trigger error');

    // Act
    component.onSubmit();
    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/`);
    req.flush(
      { detail: 'Service unavailable' },
      { status: 503, statusText: 'Service Unavailable' }
    );
    tick(200);

    // Assert
    const errorMessage = component.messages()[component.messages().length - 1];
    expect(errorMessage?.isError).toBeTrue();
    expect(errorMessage?.content).toContain('Service unavailable');
    tick(200);
    expect(component.isSending()).toBeFalse();
  }));

  it('creates a new topic and loads it', () => {
    // Arrange
    component.newTopicName.set('Feature A');

    // Act
    component.createTopic();
    const req = httpMock.expectOne(`${environment.apiUrl}/topics/`);
    req.flush({
      id: 2,
      name: 'Feature A',
      message_count: 0,
      messages: [],
    });
    const detailReq = httpMock.expectOne(`${environment.apiUrl}/topics/2/`);
    detailReq.flush({ id: 2, name: 'Feature A', message_count: 0, messages: [] });
    const listReq = httpMock.expectOne(`${environment.apiUrl}/topics/`);
    listReq.flush({
      topics: [
        { id: 1, name: 'Default', message_count: 0 },
        { id: 2, name: 'Feature A', message_count: 0 },
      ],
    });

    // Assert
    expect(component.topics().length).toBe(2);
    expect(component.selectedTopicId()).toBe(2);
    expect(component.messages().length).toBe(0);
  });

  it('loads topics from the API and selects the most recent when none is chosen', () => {
    // Arrange
    component.selectedTopicId.set(null);

    // Act
    component.loadTopics();
    const listReq = httpMock.expectOne(`${environment.apiUrl}/topics/`);
    listReq.flush({
      topics: [
        { id: 5, name: 'Earlier', message_count: 2 },
        { id: 6, name: 'Latest', message_count: 4 },
      ],
    });
    const detailReq = httpMock.expectOne(`${environment.apiUrl}/topics/6/`);
    detailReq.flush({
      id: 6,
      name: 'Latest',
      message_count: 4,
      messages: [
        { role: 'user', content: 'Hi' },
        { role: 'assistant', content: 'Hello' },
      ],
    });
    
    // Assert
    expect(component.selectedTopicId()).toBe(6);
    expect(component.messages().length).toBe(2);
    expect(component.messages()[0]).toEqual(
      jasmine.objectContaining({ from: 'user', content: 'Hi' })
    );
    expect(component.topics().map((t) => t.id)).toEqual([5, 6]);
  });

  it('allows switching to another topic and loads its history', () => {
    // Arrange
    component.topics.set([
      { id: 1, name: 'Default', message_count: 0 },
      { id: 2, name: 'Follow-up', message_count: 2 },
    ]);
    component.selectedTopicId.set(1);

    // Act
    component.selectTopic(2);
    const detailReq = httpMock.expectOne(`${environment.apiUrl}/topics/2/`);
    detailReq.flush({
      id: 2,
      name: 'Follow-up',
      message_count: 2,
      messages: [
        { role: 'user', content: 'Question' },
        { role: 'assistant', content: 'Answer' },
      ],
    });

    // Assert
    expect(component.selectedTopicId()).toBe(2);
    expect(component.messages()[1]).toEqual(
      jasmine.objectContaining({ from: 'assistant', content: 'Answer' })
    );
  });
});
