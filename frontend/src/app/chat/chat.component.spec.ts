import { HttpClientTestingModule, HttpTestingController } from '@angular/common/http/testing';
import { ComponentFixture, TestBed } from '@angular/core/testing';

import { environment } from '../../environments/environment';
import { ChatComponent } from './chat.component';


describe('ChatComponent', () => {
  let fixture: ComponentFixture<ChatComponent>;
  let component: ChatComponent;
  let httpMock: HttpTestingController;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ChatComponent, HttpClientTestingModule],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatComponent);
    component = fixture.componentInstance;
    httpMock = TestBed.inject(HttpTestingController);
  });

  afterEach(() => {
    httpMock.verify();
  });

  it('sends a question to the backend and appends the assistant answer', () => {
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
    expect(component.isSending).toBeFalse();
  });

  it('does not send a request for blank input', () => {
    component.question = '   ';

    component.onSubmit();

    httpMock.expectNone(`${environment.apiUrl}/code-qa/`);
    expect(component.messages.length).toBe(0);
    expect(component.isSending).toBeFalse();
  });

  it('shows an error message when the API call fails', () => {
    component.question = 'Trigger error';

    component.onSubmit();
    const req = httpMock.expectOne(`${environment.apiUrl}/code-qa/`);
    req.flush({ detail: 'Service unavailable' }, { status: 503, statusText: 'Service Unavailable' });

    const errorMessage = component.messages[component.messages.length - 1];
    expect(errorMessage?.isError).toBeTrue();
    expect(errorMessage?.content).toContain('Service unavailable');
    expect(component.isSending).toBeFalse();
  });
});
