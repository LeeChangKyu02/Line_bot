package com.example.demo.repository;

import com.example.demo.entity.IssueReport;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;

import java.util.List;

@Repository
public interface IssueReportRepository extends JpaRepository<IssueReport, Long> {

    // 💡 특정 단체방 ID에 해당하는 과거 이슈 리스트를 최신순으로 가져오는 메서드
    List<IssueReport> findByGroupIdOrderByCreatedAtDesc(String groupId);
}