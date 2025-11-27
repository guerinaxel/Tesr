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
      ['sendQuestion', 'getTopics', 'getTopicDetail', 'createTopic', 'searchEverything']
    );

    await TestBed.configureTestingModule({
      imports: [ChatComponent, NoopAnimationsModule],
      providers: [{ provide: ChatDataService, useValue: chatDataService }],
    }).compileComponents();

    fixture = TestBed.createComponent(ChatComponent);
    component = fixture.componentInstance;

    component.topics.set([{ id: 1, name: 'Default', message_count: 0 }]);
    component.selectedTopicId.set(1);
    chatDataService.getTopicDetail.and.returnValue(
      of({ id: 1, name: 'Default', message_count: 0, messages: [], next_offset: null })
    );
    chatDataService.getTopics.and.returnValue(of({ topics: [], next_offset: null }));
  });

  it('sends a question to the backend and appends the assistant answer', fakeAsync(() => {
    component.question.set('Explain RAG');

    chatDataService.sendQuestion.and.returnValue(of({ answer: 'Contextual explanation' }));
    chatDataService.getTopicDetail.and.returnValue(
      of({ id: 1, name: 'Default', message_count: 2, messages: [], next_offset: null })
    );

    component.onSubmit();

    expect(chatDataService.sendQuestion).toHaveBeenCalledWith({
      question: 'Explain RAG',
      system_prompt: 'code expert',
      topic_id: 1,
    });
    expect(chatDataService.getTopicDetail).toHaveBeenCalledWith(1, { limit: 0 });

    expect(component.messages()[0]).toEqual(
      jasmine.objectContaining({ from: 'user', content: 'Explain RAG' })
    );
    expect(component.messages()[1]).toEqual(
      jasmine.objectContaining({ from: 'assistant', content: 'Contextual explanation' })
    );
    tick(200);
    expect(component.isSending()).toBeFalse();
  }));

  it('ignores submits while already sending', () => {
    component.question.set('Already sending');
    component.isSending.set(true);

    component.onSubmit();

    expect(chatDataService.sendQuestion).not.toHaveBeenCalled();
  });

  it('sends a custom prompt when selected', () => {
    component.question.set('Customise the system');
    component.systemPrompt.set('custom');
    component.customPrompt.set('You are concise');

    chatDataService.sendQuestion.and.returnValue(of({ answer: 'Acknowledged' }));
    chatDataService.getTopicDetail.and.returnValue(
      of({ id: 1, name: 'Default', message_count: 2, messages: [], next_offset: null })
    );

    component.onSubmit();

    expect(chatDataService.sendQuestion).toHaveBeenCalledWith({
      question: 'Customise the system',
      system_prompt: 'custom',
      custom_prompt: 'You are concise',
      topic_id: 1,
    });
  });

  it('sends the message when pressing ctrl+space with content', () => {
    component.question.set('Quick send');

    chatDataService.sendQuestion.and.returnValue(of({ answer: 'Delivered' }));
    chatDataService.getTopicDetail.and.returnValue(
      of({ id: 1, name: 'Default', message_count: 2, messages: [], next_offset: null })
    );

    component.onSpaceSend(
      new KeyboardEvent('keydown', { key: ' ', ctrlKey: true })
    );

    expect(chatDataService.sendQuestion).toHaveBeenCalledWith({
      question: 'Quick send',
      system_prompt: 'code expert',
      topic_id: 1,
    });

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

  it('does not send on keyboard shortcut when the message is empty', () => {
    component.question.set('   ');

    component.onSpaceSend(
      new KeyboardEvent('keydown', { key: ' ', ctrlKey: true })
    );

    expect(chatDataService.sendQuestion).not.toHaveBeenCalled();
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
      of({ id: 2, name: 'Feature A', message_count: 0, messages: [], next_offset: null })
    );
    chatDataService.getTopicDetail.and.returnValue(
      of({ id: 2, name: 'Feature A', message_count: 0, messages: [], next_offset: null })
    );
    chatDataService.getTopics.and.returnValue(
      of({
        topics: [
          { id: 1, name: 'Default', message_count: 0 },
          { id: 2, name: 'Feature A', message_count: 0 },
        ],
        next_offset: null,
      })
    );

    component.createTopic();

    expect(chatDataService.createTopic).toHaveBeenCalledWith('Feature A');

    expect(component.topics().length).toBe(2);
    expect(component.selectedTopicId()).toBe(2);
    expect(component.messages().length).toBe(0);
  });

  it('ignores topic creation when name is blank', () => {
    component.newTopicName.set('   ');

    component.createTopic();

    expect(chatDataService.createTopic).not.toHaveBeenCalled();
  });

  it('refreshes topic metadata and ignores null topic ids', () => {
    const getTopicDetailSpy = chatDataService.getTopicDetail.and.returnValue(
      of({ id: 1, name: 'Updated', message_count: 5, messages: [], next_offset: null })
    );

    component.topics.set([{ id: 1, name: 'Default', message_count: 1 }]);
    component['refreshTopicMetadata'](null);
    expect(getTopicDetailSpy).not.toHaveBeenCalled();

    component['refreshTopicMetadata'](1);

    expect(getTopicDetailSpy).toHaveBeenCalledWith(1, { limit: 0 });
    expect(component.topics()[0]).toEqual(
      jasmine.objectContaining({ name: 'Updated', message_count: 5 })
    );
  });

  it('loads topics from the API and selects the most recent when none is chosen', () => {
    component.selectedTopicId.set(null);
    component.topics.set([]);

    chatDataService.getTopics.and.returnValue(
      of({
        topics: [
          { id: 6, name: 'Latest', message_count: 4 },
          { id: 5, name: 'Earlier', message_count: 2 },
        ],
        next_offset: null,
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
        next_offset: null,
      })
    );

    component.loadTopics(null, true);

    expect(component.selectedTopicId()).toBe(6);
    expect(component.messages().length).toBe(2);
    expect(component.messages()[0]).toEqual(
      jasmine.objectContaining({ from: 'user', content: 'Hi' })
    );
    expect(component.topics().map((t) => t.id)).toEqual([6, 5]);
    expect(chatDataService.getTopicDetail).toHaveBeenCalledWith(6, {
      offset: 0,
      limit: 30,
    });
  });

  it('selects a requested topic when provided', () => {
    chatDataService.getTopics.and.returnValue(
      of({
        topics: [{ id: 3, name: 'Requested', message_count: 1 }],
        next_offset: null,
      })
    );
    chatDataService.getTopicDetail.and.returnValue(
      of({
        id: 3,
        name: 'Requested',
        message_count: 1,
        messages: [],
        next_offset: null,
      })
    );

    component.loadTopics(3);

    expect(component.selectedTopicId()).toBe(3);
    expect(chatDataService.getTopicDetail).toHaveBeenCalledWith(3, {
      offset: 0,
      limit: 30,
    });
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
        next_offset: null,
      })
    );

    component.selectTopic(2);

    expect(component.selectedTopicId()).toBe(2);
    expect(component.messages()[1]).toEqual(
      jasmine.objectContaining({ from: 'assistant', content: 'Answer' })
    );
  });

  it('does not reload the same topic unless forced', () => {
    component.topics.set([
      { id: 1, name: 'Default', message_count: 0 },
      { id: 2, name: 'Follow-up', message_count: 2 },
    ]);

    component.selectedTopicId.set(2);
    component.selectTopic(2);

    expect(chatDataService.getTopicDetail).not.toHaveBeenCalled();

    chatDataService.getTopicDetail.and.returnValue(
      of({ id: 2, name: 'Follow-up', message_count: 2, messages: [], next_offset: null })
    );

    component.selectTopic(2, true);

    expect(chatDataService.getTopicDetail).toHaveBeenCalledWith(2, {
      offset: 0,
      limit: 30,
    });
  });

  it('clears messages when topic detail fails to load', () => {
    component.selectedTopicId.set(1);
    component.messages.set([
      { id: 1, from: 'user', content: 'Question' },
      { id: 2, from: 'assistant', content: 'Answer' },
    ]);

    chatDataService.getTopicDetail.and.returnValue(
      throwError(() => new Error('Nope'))
    );

    component.selectTopic(1, true);

    expect(component.messages().length).toBe(0);
  });

  it('sends on ctrl+space or meta+space but not while sending', () => {
    component.question.set('Meta send');
    chatDataService.sendQuestion.and.returnValue(of({ answer: 'done' }));
    chatDataService.getTopicDetail.and.returnValue(
      of({ id: 1, name: 'Default', message_count: 0, messages: [], next_offset: null })
    );

    component.onSpaceSend(
      new KeyboardEvent('keydown', { key: ' ', metaKey: true })
    );

    expect(chatDataService.sendQuestion).toHaveBeenCalledTimes(1);

    component.isSending.set(true);
    component.question.set('Blocked');

    component.onSpaceSend(
      new KeyboardEvent('keydown', { key: ' ', ctrlKey: true })
    );

    expect(chatDataService.sendQuestion).toHaveBeenCalledTimes(1);
  });

  it('loads more topics when the viewport nears the end', () => {
    chatDataService.getTopics.and.returnValue(
      of({ topics: [{ id: 1, name: 'Default', message_count: 0 }], next_offset: 20 })
    );
    component.loadTopics();
    chatDataService.getTopics.calls.reset();

    chatDataService.getTopics.and.returnValue(
      of({ topics: [{ id: 2, name: 'Next', message_count: 1 }], next_offset: null })
    );

    component.onTopicsScrolled(component.topics().length - 1);

    expect(chatDataService.getTopics).toHaveBeenCalledWith({
      offset: 20,
      limit: 20,
    });
    expect(component.topics().length).toBe(2);
  });

  it('loads additional messages when scrolling the conversation', () => {
    chatDataService.getTopicDetail.and.returnValue(
      of({
        id: 1,
        name: 'Default',
        message_count: 3,
        messages: [
          { role: 'user', content: 'One' },
          { role: 'assistant', content: 'Two' },
        ],
        next_offset: 2,
      })
    );

    component.selectTopic(1, true);
    chatDataService.getTopicDetail.calls.reset();

    chatDataService.getTopicDetail.and.returnValue(
      of({
        id: 1,
        name: 'Default',
        message_count: 3,
        messages: [{ role: 'user', content: 'Three' }],
        next_offset: null,
      })
    );

    component.onMessagesScrolled(component.messages().length - 1);

    expect(chatDataService.getTopicDetail).toHaveBeenCalledWith(1, {
      offset: 2,
      limit: 30,
    });
    expect(component.messages().length).toBe(3);
  });

  it('handles topic load failures gracefully', () => {
    component.topics.set([
      { id: 1, name: 'Default', message_count: 0 },
      { id: 2, name: 'Follow-up', message_count: 2 },
    ]);

    chatDataService.getTopics.and.returnValue(throwError(() => new Error('fail')));

    component.loadTopics();

    expect(component.topics().length).toBe(0);
    expect(component.selectedTopicId()).toBeNull();
    expect(component.messages().length).toBe(0);
  });

  it('does not request topics while loading or when no more pages exist', () => {
    (component as any).topicsLoading = true;

    component.loadTopics();

    expect(chatDataService.getTopics).not.toHaveBeenCalled();

    (component as any).topicsLoading = false;
    (component as any).hasMoreTopics = false;

    component.loadTopics();

    expect(chatDataService.getTopics).not.toHaveBeenCalled();
  });

  it('clears selection when topic list is empty', () => {
    component.selectedTopicId.set(1);
    component.messages.set([
      { id: 1, from: 'user', content: 'Question' },
      { id: 2, from: 'assistant', content: 'Answer' },
    ]);

    chatDataService.getTopics.and.returnValue(of({ topics: [], next_offset: null }));

    component.loadTopics(null, true);

    expect(component.topics()).toEqual([]);
    expect(component.selectedTopicId()).toBeNull();
    expect(component.messages().length).toBe(0);
  });

  it('does not load messages while fetching or when no next page is available', () => {
    (component as any).messagesLoading = true;

    (component as any).loadMessages(1);

    expect(chatDataService.getTopicDetail).not.toHaveBeenCalled();

    (component as any).messagesLoading = false;
    (component as any).hasMoreMessages = false;

    (component as any).loadMessages(1);

    expect(chatDataService.getTopicDetail).not.toHaveBeenCalled();
  });

  it('ignores message scrolls when no topic is selected', () => {
    component.selectedTopicId.set(null);

    component.onMessagesScrolled(10);

    expect(chatDataService.getTopicDetail).not.toHaveBeenCalled();
  });

  it('debounces topic search input and captures results', fakeAsync(() => {
    chatDataService.searchEverything.and.returnValue(
      of({
        topics: { items: [{ id: 7, name: 'Match', message_count: 1 }], next_offset: null },
        questions: { items: [], next_offset: null },
        answers: { items: [], next_offset: null },
      })
    );

    component.onTopicSearchChange('  search  ');

    tick(400);
    expect(chatDataService.searchEverything).not.toHaveBeenCalled();

    tick(100);

    expect(chatDataService.searchEverything).toHaveBeenCalledWith('search', { limit: 5 });
    expect(component.topicSearchLoading()).toBeFalse();
    expect(component.topicSearchResults()[0]).toEqual(
      jasmine.objectContaining({ id: 7, name: 'Match' })
    );
  }));

  it('clears topic search results for empty input', fakeAsync(() => {
    component.topicSearchResults.set([{ id: 1, name: 'Keep', message_count: 1 }]);
    component.topicSearchLoading.set(true);

    component.onTopicSearchChange('   ');

    tick(600);

    expect(chatDataService.searchEverything).not.toHaveBeenCalled();
    expect(component.topicSearchResults()).toEqual([]);
    expect(component.topicSearchLoading()).toBeFalse();
  }));

  it('resets topic search state when the API errors', fakeAsync(() => {
    chatDataService.searchEverything.and.returnValue(
      throwError(() => new Error('fail'))
    );

    component.onTopicSearchChange('oops');
    tick(500);

    expect(component.topicSearchResults()).toEqual([]);
    expect(component.topicSearchLoading()).toBeFalse();
  }));

  it('opens and closes the topic search overlay and tracks list entries', fakeAsync(() => {
    component.topicSearchResults.set([{ id: 4, name: 'Focus', message_count: 0 }]);
    component.topicSearchQuery.set('Focus');

    component.openTopicSearch();
    expect(component.isTopicSearchVisible()).toBeTrue();

    tick();

    component.closeTopicSearch();

    expect(component.isTopicSearchVisible()).toBeFalse();
    expect(component.topicSearchQuery()).toBe('');
    expect(component.topicSearchResults()).toEqual([]);
    expect(component.topicTrackBy(0, { id: 3, name: 'Track', message_count: 0 })).toBe(3);
    expect(
      component.messageTrackBy(0, { id: 7, from: 'assistant', content: 'Answer' })
    ).toBe(7);
  }));
});
