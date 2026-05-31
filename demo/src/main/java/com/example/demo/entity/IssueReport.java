package com.example.demo.entity;

import jakarta.persistence.*;
import lombok.Getter;
import lombok.NoArgsConstructor; // 롬복 기본 생성자 자동 생성
import lombok.Setter;
import java.time.LocalDateTime;

@Entity
@Table(name = "issue_reports")
@Getter
@Setter
@NoArgsConstructor // 💡 매개변수 없는 기본 생성자를 자동으로 만들어 줍니다.
public class IssueReport {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    // 라인 단체방 고유 ID
    @Column(nullable = false)
    private String groupId;

    // 이슈를 올린 유저 ID
    private String userId;

    // 팀원이 제보한 버그 내용 (텍스트)
    @Column(columnDefinition = "TEXT", nullable = false)
    private String issueContent;

    // 등록 시간
    private LocalDateTime createdAt;

    @PrePersist
    public void prePersist() {
        this.createdAt = LocalDateTime.now();
    }

    // 💡 테스트 및 저장을 위한 커스텀 생성자
    public IssueReport(String groupId, String userId, String issueContent) {
        this.groupId = groupId;
        this.userId = userId;
        this.issueContent = issueContent;
    }
}