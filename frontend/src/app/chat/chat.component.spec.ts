import { ComponentFixture, TestBed, fakeAsync, tick } from '@angular/core/testing';
import { NoopAnimationsModule } from '@angular/platform-browser/animations';
import { of, throwError } from 'rxjs';

import { ChatComponent } from './chat.component';
import { ChatDataService } from './chat-data.service';


describe('ChatComponent', () => {
  let fixture: ComponentFixture<ChatComponent>;
  let component: ChatComponent;
  let chatDataService: jasmine.SpyObj<ChatDataService>;

  beforeEach(async () => {
    chatDataService = jasmine.createSpyObj<ChatDataService>(
      'ChatDataService',
      ['sendQuestion', 'getTopics', 'getTopicDetail', 'createTopic']
    );

    await TestBed.configureTestingModule({
      imports: [ChatComponent, NoopAnimationsModule],
      providers: [{ provide: ChatDataService, useValue: chatDataService }],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatComponent);
    component = fixture.componentInstance;

    component.topics.set([{ id: 1, name: 'Default', message_count: 0 }]);
    component.selectedTopicId.set(1);
  });

  it('sends a question to the backend and appends the assistant answer', fakeAsync(() => {
    component.question.set('Explain RAG');

    chatDataService.sendQuestion.and.returnValue(of({ answer: 'Contextual explanation' }));
    chatDataService.getTopicDetail.and.returnValue(
      of({ id: 1, name: 'Default', message_count: 2, messages: [] })
    );

    component.onSubmit();

    expect(chatDataService.sendQuestion).toHaveBeenCalledWith({
      question: 'Explain RAG',
      system_prompt: 'code expert',
      topic_id: '1',
    });
    expect(chatDataService.getTopicDetail).toHaveBeenCalledWith(1);

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

    chatDataService.sendQuestion.and.returnValue(of({ answer: 'Acknowledged' }));
    chatDataService.getTopicDetail.and.returnValue(
      of({ id: 1, name: 'Default', message_count: 2, messages: [] })
    );

    component.onSubmit();

    expect(chatDataService.sendQuestion).toHaveBeenCalledWith({
      question: 'Customise the system',
      system_prompt: 'custom',
      custom_prompt: 'You are concise',
      topic_id: '1',
    });
  });

  it('sends the message when pressing ctrl+space with content', () => {
    component.question.set('Quick send');

    chatDataService.sendQuestion.and.returnValue(of({ answer: 'Delivered' }));
    chatDataService.getTopicDetail.and.returnValue(
      of({ id: 1, name: 'Default', message_count: 2, messages: [] })
    );

    component.onSpaceSend(
      new KeyboardEvent('keydown', { key: ' ', ctrlKey: true })
    );

    expect(component.messages()[0]).toEqual(
      jasmine.objectContaining({ from: 'user', content: 'Quick send' })
    );
    expect(component.messages()[1]).toEqual(
      jasmine.objectContaining({ from: 'assistant', content: 'Delivered' })
    );
  });

  it('does not send the message when pressing space without modifiers', () => {
    component.question.set('Should stay');

    component.onSpaceSend(new KeyboardEvent('keydown', { key: ' ' }));

    expect(chatDataService.sendQuestion).not.toHaveBeenCalled();
    expect(component.messages().length).toBe(0);
    expect(component.isSending()).toBeFalse();
  });

  it('does not send when custom prompt is missing', () => {
    component.question.set('Should block');
    component.systemPrompt.set('custom');
    component.customPrompt.set('   ');

    component.onSubmit();

    expect(chatDataService.sendQuestion).not.toHaveBeenCalled();
    expect(component.messages().length).toBe(0);
    expect(component.isSending()).toBeFalse();
  });

  it('does not send a request for blank input', () => {
    component.question.set('   ');

    component.onSubmit();

    expect(chatDataService.sendQuestion).not.toHaveBeenCalled();
    expect(component.messages().length).toBe(0);
    expect(component.isSending()).toBeFalse();
  });

  it('shows an error message when the API call fails', fakeAsync(() => {
    component.question.set('Trigger error');

    chatDataService.sendQuestion.and.returnValue(
      throwError(() => ({ error: { detail: 'Service unavailable' } }))
    );

    component.onSubmit();

    const errorMessage = component.messages()[component.messages().length - 1];
    expect(errorMessage?.isError).toBeTrue();
    expect(errorMessage?.content).toContain('Service unavailable');
    tick(200);
    expect(component.isSending()).toBeFalse();
  }));

  it('creates a new topic and loads it', () => {
    component.newTopicName.set('Feature A');

    chatDataService.createTopic.and.returnValue(
      of({ id: 2, name: 'Feature A', message_count: 0, messages: [] })
    );
    chatDataService.getTopicDetail.and.returnValue(
      of({ id: 2, name: 'Feature A', message_count: 0, messages: [] })
    );
    chatDataService.getTopics.and.returnValue(
      of({
        topics: [
          { id: 1, name: 'Default', message_count: 0 },
          { id: 2, name: 'Feature A', message_count: 0 },
        ],
      })
    );

    component.createTopic();

    expect(chatDataService.createTopic).toHaveBeenCalledWith('Feature A');

    expect(component.topics().length).toBe(2);
    expect(component.selectedTopicId()).toBe(2);
    expect(component.messages().length).toBe(0);
  });

  it('loads topics from the API and selects the most recent when none is chosen', () => {
    component.selectedTopicId.set(null);

    chatDataService.getTopics.and.returnValue(
      of({
        topics: [
          { id: 5, name: 'Earlier', message_count: 2 },
          { id: 6, name: 'Latest', message_count: 4 },
        ],
      })
    );
    chatDataService.getTopicDetail.and.returnValue(
      of({
        id: 6,
        name: 'Latest',
        message_count: 4,
        messages: [
          { role: 'user', content: 'Hi' },
          { role: 'assistant', content: 'Hello' },
        ],
      })
    );

    component.loadTopics();

    expect(component.selectedTopicId()).toBe(6);
    expect(component.messages().length).toBe(2);
    expect(component.messages()[0]).toEqual(
      jasmine.objectContaining({ from: 'user', content: 'Hi' })
    );
    expect(component.topics().map((t) => t.id)).toEqual([5, 6]);
  });

  it('allows switching to another topic and loads its history', () => {
    component.topics.set([
      { id: 1, name: 'Default', message_count: 0 },
      { id: 2, name: 'Follow-up', message_count: 2 },
    ]);
    component.selectedTopicId.set(1);

    chatDataService.getTopicDetail.and.returnValue(
      of({
        id: 2,
        name: 'Follow-up',
        message_count: 2,
        messages: [
          { role: 'user', content: 'Question' },
          { role: 'assistant', content: 'Answer' },
        ],
      })
    );

    component.selectTopic(2);

    expect(component.selectedTopicId()).toBe(2);
    expect(component.messages()[1]).toEqual(
      jasmine.objectContaining({ from: 'assistant', content: 'Answer' })
    );
  });
});
