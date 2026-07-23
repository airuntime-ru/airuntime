"use client";

import { useEffect, useRef } from "react";
import { useVirtualizer } from "@tanstack/react-virtual";

import { MessageItem } from "@/components/chat/message-item";
import type { ChatMessage } from "@/lib/chat-stream-runtime";

const ESTIMATE_PX = 120;

type MessageListProps = {
  messages: ChatMessage[];
  loading: boolean;
  stickToBottom: boolean;
  onStickChange: (nearBottom: boolean) => void;
  bottomSlot?: React.ReactNode;
};

export function MessageList({
  messages,
  loading,
  stickToBottom,
  onStickChange,
  bottomSlot,
}: MessageListProps) {
  const parentRef = useRef<HTMLDivElement>(null);

  const virtualizer = useVirtualizer({
    count: messages.length,
    getScrollElement: () => parentRef.current,
    estimateSize: () => ESTIMATE_PX,
    overscan: 8,
    measureElement:
      typeof window !== "undefined" && !navigator.userAgent.includes("Firefox")
        ? (element) => element.getBoundingClientRect().height
        : undefined,
  });

  useEffect(() => {
    const node = parentRef.current;
    if (!node) return undefined;
    const onScroll = () => {
      const distance = node.scrollHeight - node.scrollTop - node.clientHeight;
      onStickChange(distance < 140);
    };
    node.addEventListener("scroll", onScroll, { passive: true });
    return () => node.removeEventListener("scroll", onScroll);
  }, [onStickChange]);

  const lastContentLen = messages[messages.length - 1]?.content?.length ?? 0;

  useEffect(() => {
    if (!stickToBottom || messages.length === 0) return;
    virtualizer.scrollToIndex(messages.length - 1, { align: "end" });
  }, [stickToBottom, messages.length, lastContentLen, loading, virtualizer]);

  if (messages.length === 0) {
    return (
      <div ref={parentRef} className="flex-1 overflow-y-auto">
        <div className="mx-auto flex min-h-[40vh] w-full max-w-3xl flex-col items-center justify-center px-4 text-center sm:px-6">
          <p className="text-lg font-medium text-[var(--ar-black)]">Чем помочь?</p>
          <p className="mt-2 max-w-sm text-sm text-[var(--ar-stone)]">
            Опишите сайт или бота — AIRuntime соберёт и задеплоит проект.
          </p>
        </div>
        {bottomSlot}
      </div>
    );
  }

  const items = virtualizer.getVirtualItems();

  return (
    <div ref={parentRef} className="flex-1 overflow-y-auto" data-tour="chat-message-list">
      <div className="mx-auto w-full max-w-3xl px-4 py-6 pb-8 sm:px-6">
        <div
          className="relative w-full"
          style={{ height: `${virtualizer.getTotalSize()}px` }}
        >
          {items.map((item) => {
            const message = messages[item.index];
            const isStreaming =
              loading && item.index === messages.length - 1 && message.role === "assistant";
            return (
              <div
                key={item.key}
                data-index={item.index}
                ref={virtualizer.measureElement}
                className="absolute left-0 top-0 w-full pb-8"
                style={{ transform: `translateY(${item.start}px)` }}
              >
                <MessageItem message={message} isStreaming={isStreaming} />
              </div>
            );
          })}
        </div>
        {bottomSlot}
      </div>
    </div>
  );
}
