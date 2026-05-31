package com.example.demo.dto; // 본인 패키지 경로에 맞게 수정

import lombok.Getter;
import lombok.ToString;
import java.util.List;

@Getter
@ToString
public class LineWebhookDto {
    private String destination;
    private List<Event> events;

    @Getter
    @ToString
    public static class Event {
        private String type;
        private String replyToken;
        private Source source;
        private Message message;
        private long timestamp;
    }

    @Getter
    @ToString
    public static class Source {
        private String type;
        private String groupId;
        private String userId;
    }

    @Getter
    @ToString
    public static class Message {
        private String id;
        private String type;
        private String text; // 💡 우리가 가져올 실제 텍스트 ("Test")
    }
}