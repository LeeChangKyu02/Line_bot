package com.example.demo.controller;

import com.example.demo.dto.LineReplyDto;
import com.example.demo.dto.LineWebhookDto;
import com.example.demo.entity.IssueReport;
import com.example.demo.repository.IssueReportRepository;
import com.example.demo.service.GeminiService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;
import org.springframework.web.client.RestTemplate;

import java.util.Collections;
import java.util.List;

@RestController
@RequestMapping("/api/webhook")
public class LineWebhookController {

    @Autowired
    private GeminiService geminiService;

    @Autowired
    private IssueReportRepository issueReportRepository;

    @Value("${line.bot.channel-token}")
    private String lineChannelToken;

    private final String LINE_REPLY_URL = "https://api.line.me/v2/bot/message/reply";

    @PostMapping
    public ResponseEntity<String> handleLineWebhook(@RequestBody LineWebhookDto webhookDto) {

        if (webhookDto.getEvents() != null && !webhookDto.getEvents().isEmpty()) {
            for (LineWebhookDto.Event event : webhookDto.getEvents()) {

                if ("message".equals(event.getType()) && "text".equals(event.getMessage().getType())) {
                    String replyToken = event.getReplyToken(); // 💡 답장할 때 필요한 핵심 토큰
                    String groupId = event.getSource().getGroupId();
                    String userId = event.getSource().getUserId();
                    String userMessage = event.getMessage().getText();

                    // 1️⃣ DB에서 과거 이슈 리스트 조회
                    List<IssueReport> pastIssues = issueReportRepository.findByGroupIdOrderByCreatedAtDesc(groupId);

                    StringBuilder pastIssuesBuilder = new StringBuilder();
                    for (IssueReport report : pastIssues) {
                        pastIssuesBuilder.append("[").append(report.getIssueContent()).append("] ");
                    }
                    String pastIssuesJson = pastIssuesBuilder.toString();

                    // 2️⃣ 가짜 제미나이 서비스를 통해 중복 분석 판정
                    String aiResult = geminiService.analyzeMessage(userMessage, pastIssuesJson);

                    String replyMessageText = "";

                    // 3️⃣ 결과에 따른 비즈니스 로직 처리 및 답장 문구 생성
                    if ("신규".equals(aiResult)) {
                        IssueReport newIssue = new IssueReport(groupId, userId, userMessage);
                        issueReportRepository.save(newIssue);
                        replyMessageText = "✅ [신규 이슈 등록]\n새로운 버그 리포트가 DB에 안전하게 저장되었습니다.";
                    } else {
                        replyMessageText = "🚨 [경고: 중복 이슈 발견]\n방금 제보하신 내용은 이미 기존에 등록된 이슈와 매우 유사합니다!\n동일 버그인지 확인해 주세요.";
                    }

                    // 4️⃣ 💡 LINE 서버로 진짜 답장 메시지 전송 (HTTP POST)
                    sendLineReply(replyToken, replyMessageText);
                }
            }
        }
        return ResponseEntity.ok("OK");
    }

    // LINE API 호출을 담당하는 헬퍼 메서드
    private void sendLineReply(String replyToken, String text) {
        RestTemplate restTemplate = new RestTemplate();

        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Authorization", "Bearer " + lineChannelToken.trim()); // 내 채널 토큰 주입

        LineReplyDto.Message messageObj = new LineReplyDto.Message("text", text);
        LineReplyDto replyPayload = new LineReplyDto(replyToken, Collections.singletonList(messageObj));

        HttpEntity<LineReplyDto> entity = new HttpEntity<>(replyPayload, headers);

        try {
            restTemplate.postForEntity(LINE_REPLY_URL, entity, String.class);
            System.out.println("[LINE 답장 전송 완료]");
        } catch (Exception e) {
            System.err.println("[LINE 답장 전송 실패]: " + e.getMessage());
            e.printStackTrace();
        }
    }
}