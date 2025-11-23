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
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('sends a question to the backend and appends the assistant answer', fakeAsync(() => {
    component.question = 'Explain RAG';

    component.onSubmit();

    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/`);
    expect(req.request.method).toBe('POST');
    expect(req.request.body).toEqual({ question: 'Explain RAG' });

    req.flush({ answer: 'Contextual explanation' });

    expect(component.messages[0]).toEqual(
      jasmine.objectContaining({ from: 'user', content: 'Explain RAG' })
    );
    expect(component.messages[1]).toEqual(
      jasmine.objectContaining({ from: 'assistant', content: 'Contextual explanation' })
    );
    tick(200);
    expect(component.isSending).toBeFalse();
  }));

  it('sends the message when pressing ctrl+space with content', () => {
    component.question = 'Quick send';

    component.onSpaceSend(
      new KeyboardEvent('keydown', { key: ' ', ctrlKey: true })
    );

    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/`);
    req.flush({ answer: 'Delivered' });

    expect(component.messages[0]).toEqual(
      jasmine.objectContaining({ from: 'user', content: 'Quick send' })
    );
    expect(component.messages[1]).toEqual(
      jasmine.objectContaining({ from: 'assistant', content: 'Delivered' })
    );
  });

  it('does not send the message when pressing space without modifiers', () => {
    component.question = 'Should stay';

    component.onSpaceSend(new KeyboardEvent('keydown', { key: ' ' }));

    httpMock.expectNone(`${environment.apiUrl}/code-qa/`);
    expect(component.messages.length).toBe(0);
    expect(component.isSending).toBeFalse();
  });

  it('does not send a request for blank input', () => {
    component.question = '   ';

    component.onSubmit();

    httpMock.expectNone(`${environment.apiUrl}/code-qa/`);
    expect(component.messages.length).toBe(0);
    expect(component.isSending).toBeFalse();
  });

  it('shows an error message when the API call fails', fakeAsync(() => {
    component.question = 'Trigger error';

    component.onSubmit();
    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/`);
    req.flush({ detail: 'Service unavailable' }, { status: 503, statusText: 'Service Unavailable' });

    const errorMessage = component.messages[component.messages.length - 1];
    expect(errorMessage?.isError).toBeTrue();
    expect(errorMessage?.content).toContain('Service unavailable');
    tick(200);
    expect(component.isSending).toBeFalse();
  }));
});
