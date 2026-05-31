package com.example.demo.dto;

import lombok.AllArgsConstructor;
import lombok.Getter;
import lombok.Setter;
import java.util.List;

@Getter
@Setter
@AllArgsConstructor
public class LineReplyDto {
    private String replyToken; // 라인 이벤트에서 받아온 답장용 1회성 토큰
    private List<Message> messages;

    @Getter
    @Setter
    @AllArgsConstructor
    public static class Message {
        private String type; // text 고정
        private String text; // 실제 팀원들에게 보여줄 답장 내용
    }
}