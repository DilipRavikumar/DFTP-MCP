package com.example.dftp.controller;

import com.example.dftp.model.ExceptionDTO;
import com.example.dftp.model.GenericAck;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import java.util.List;
import java.util.UUID;

@RestController
@RequestMapping("/api/exceptions")
public class ExceptionController {


    @PostMapping("/raise")
    public ResponseEntity<GenericAck> raise(@RequestBody ExceptionDTO ex) {
        String id = "EX-" + UUID.randomUUID().toString().substring(0,8);
        return ResponseEntity.ok(new GenericAck("EXCEPTION_RAISED", id));
    }

    @GetMapping("")
    public ResponseEntity<List<ExceptionDTO>> list() {
        ExceptionDTO e = new ExceptionDTO("EX-0001","canonical","T-1111","RULE_FAIL","Rule X failed","HIGH",10000.0,"OPEN");
        return ResponseEntity.ok(List.of(e));
    }
}
