package com.example.demo.service;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Service;
import org.springframework.web.client.RestTemplate;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Service
public class GeminiService {

    @Value("${openai.api.key}")
    private String apiKey;

    // 💡 OpenAI 공식 Chat API 엔드포인트 주소
    private final String OPENAI_URL = "https://api.openai.com/v1/chat/completions";

    public String analyzeMessage(String userMessage, String pastIssuesJson) {
        RestTemplate restTemplate = new RestTemplate();

        // 1. HTTP 헤더 설정 (Bearer 토큰 인증)
        HttpHeaders headers = new HttpHeaders();
        headers.setContentType(MediaType.APPLICATION_JSON);
        headers.set("Authorization", "Bearer " + apiKey.trim());

        // 2. 🤖 AI에게 내릴 프롬프트 지시사항 조립
        String systemPrompt = "너는 소프트웨어 QA 분석가야. 아래 제공되는 '과거 이슈 리스트'와 팀원이 새로 제보한 '현재 메시지'의 의미를 분석해줘.\n\n"
                + " [과거 이슈 리스트]: " + (pastIssuesJson.isEmpty() ? "없음" : pastIssuesJson) + "\n"
                + " [현재 메시지]: " + userMessage + "\n\n"
                + "만약 현재 메시지가 과거 이슈 리스트에 있는 내용과 현상, 원인 측면에서 '의미상 유사하거나 중복'된다면 반드시 딱 두 글자 '중복'이라고만 답해줘.\n"
                + "만약 과거 리스트와 겹치지 않는 새로운 내용이거나 리스트가 완전히 비어있다면 반드시 딱 두 글자 '신규'라고만 답해줘.\n"
                + "설명이나 다른 말은 절대 하지 말고 오직 '중복' 또는 '신규' 둘 중 하나만 출력해.";

        // 3. OpenAI 규격(Model, Messages)에 맞는 JSON 페이로드 생성 (Map 구조)
        Map<String, Object> body = new HashMap<>();
        body.put("model", "gpt-4o-mini"); // 💡 가성비와 속도가 가장 뛰어난 미니 모델
        body.put("temperature", 0.0);    // 분석 결과의 일관성을 위해 창의성을 0으로 고정

        List<Map<String, String>> messages = new ArrayList<>();
        Map<String, String> message = new HashMap<>();
        message.put("role", "user");
        message.put("content", systemPrompt);
        messages.add(message);

        body.put("messages", messages);

        HttpEntity<Map<String, Object>> entity = new HttpEntity<>(body, headers);

        try {
            // 4. OpenAI 서버로 API 호출
            ResponseEntity<Map> response = restTemplate.postForEntity(OPENAI_URL, entity, Map.class);

            // 5. OpenAI 응답 JSON 파싱 (choices[0].message.content)
            Map<String, Object> responseBody = response.getBody();
            if (responseBody != null && responseBody.containsKey("choices")) {
                List<Map<String, Object>> choices = (List<Map<String, Object>>) responseBody.get("choices");
                Map<String, Object> firstChoice = choices.get(0);
                Map<String, Object> messageMap = (Map<String, Object>) firstChoice.get("message");
                String aiText = (String) messageMap.get("content");

                return aiText.trim();
            }
        } catch (Exception e) {
            System.err.println("[OpenAI API 호출 에러]: " + e.getMessage());
        }

        // 에러 발생 시 시스템 안전을 위해 신규로 처리하여 DB에 저장하도록 유도
        return "신규";
    }
}