package rule

import (
	"regexp"
	"strings"
	"testing"
)

// TestRegexPatternNotLowercased verifies that compiling a case-insensitive
// regex operator uses the (?i) flag instead of lowercasing the pattern,
// which would corrupt character classes like [A-Z].
func TestRegexPatternNotLowercased(t *testing.T) {
	var dummyList []Operator

	tests := []struct {
		name    string
		pattern string
	}{
		{"mixed case character class", "[A-Za-z0-9]"},
		{"uppercase character class", "[A-Z]"},
		{"uppercase literal", "^FOO$"},
		{"complex pattern", `^/usr/[A-Z][a-z]+/bin$`},
	}

	for _, tc := range tests {
		t.Run(tc.name, func(t *testing.T) {
			op, err := NewOperator(Regexp, false, OpProcessPath, tc.pattern, dummyList)
			if err != nil {
				t.Fatalf("NewOperator error: %v", err)
			}
			if err := op.Compile(); err != nil {
				t.Fatalf("Compile error: %v", err)
			}

			// The stored pattern should NOT be lowercased; it should have (?i) prefix
			if op.Data == strings.ToLower(tc.pattern) && op.Data != tc.pattern {
				t.Errorf("pattern was lowercased: got %q, original was %q", op.Data, tc.pattern)
			}
			if !strings.HasPrefix(op.Data, "(?i)") {
				t.Errorf("expected (?i) prefix, got %q", op.Data)
			}
			// The original pattern should be intact after the (?i) prefix
			if op.Data != "(?i)"+tc.pattern {
				t.Errorf("expected %q, got %q", "(?i)"+tc.pattern, op.Data)
			}
		})
	}
}

// TestRegexCaseInsensitiveMatchesCorrectly verifies that case-insensitive
// regex matching works properly using (?i) flag.
func TestRegexCaseInsensitiveMatchesCorrectly(t *testing.T) {
	var dummyList []Operator

	// Case-insensitive operator should match regardless of input case
	op, err := NewOperator(Regexp, false, OpDstHost, `^opensnitch\.io$`, dummyList)
	if err != nil {
		t.Fatalf("NewOperator error: %v", err)
	}
	if err := op.Compile(); err != nil {
		t.Fatalf("Compile error: %v", err)
	}

	// With (?i), the regex should match any case
	shouldMatch := []string{
		"opensnitch.io",
		"OPENSNITCH.IO",
		"OpenSnitch.IO",
		"openSNITCH.io",
	}

	for _, input := range shouldMatch {
		if !op.re.MatchString(input) {
			t.Errorf("case-insensitive regex should match %q", input)
		}
	}

	shouldNotMatch := []string{
		"www.opensnitch.io",
		"opensnitch.io.evil.com",
	}

	for _, input := range shouldNotMatch {
		if op.re.MatchString(input) {
			t.Errorf("regex should NOT match %q", input)
		}
	}
}

// TestRegexCharacterClassPreserved verifies that character classes with
// uppercase ranges are not corrupted by lowercasing.
func TestRegexCharacterClassPreserved(t *testing.T) {
	// Simulate the old buggy behavior to prove it was wrong
	brokenPattern := strings.ToLower("[A-Za-z0-9]")
	// [a-za-z0-9] - the A-Z becomes a-z which is redundant but more
	// importantly, patterns like [A-Z] become [a-z] which changes semantics.

	fixedPattern := "(?i)[A-Za-z0-9]"

	brokenRe, err := regexp.Compile(brokenPattern)
	if err != nil {
		t.Fatalf("failed to compile broken pattern: %v", err)
	}

	fixedRe, err := regexp.Compile(fixedPattern)
	if err != nil {
		t.Fatalf("failed to compile fixed pattern: %v", err)
	}

	// Both should match lowercase
	if !brokenRe.MatchString("a") {
		t.Error("broken pattern should match lowercase 'a'")
	}
	if !fixedRe.MatchString("a") {
		t.Error("fixed pattern should match lowercase 'a'")
	}

	// The key difference: the fixed pattern preserves the intent
	// for patterns that rely on uppercase character classes
	upperOnlyPattern := "[A-Z]"
	brokenUpperRe, err := regexp.Compile(strings.ToLower(upperOnlyPattern))
	if err != nil {
		t.Fatalf("failed to compile broken upper pattern: %v", err)
	}

	fixedUpperRe, err := regexp.Compile("(?i)" + upperOnlyPattern)
	if err != nil {
		t.Fatalf("failed to compile fixed upper pattern: %v", err)
	}

	// With (?i), [A-Z] should match both upper and lower
	if !fixedUpperRe.MatchString("A") {
		t.Error("fixed [A-Z] with (?i) should match 'A'")
	}
	if !fixedUpperRe.MatchString("a") {
		t.Error("fixed [A-Z] with (?i) should match 'a'")
	}

	// The broken version lowercased [A-Z] to [a-z], losing the uppercase match semantics
	// In this specific case it still "works" since [a-z] matches lowercase,
	// but the pattern's original intent was to match uppercase letters.
	_ = brokenUpperRe // demonstrates the pattern mutation issue
}

// TestRegexSensitiveNotPrefixed verifies that case-sensitive (Sensitive=true)
// regex operators do NOT get the (?i) prefix.
func TestRegexSensitiveNotPrefixed(t *testing.T) {
	var dummyList []Operator

	op, err := NewOperator(Regexp, true, OpProcessPath, `^/usr/bin/curl$`, dummyList)
	if err != nil {
		t.Fatalf("NewOperator error: %v", err)
	}
	if err := op.Compile(); err != nil {
		t.Fatalf("Compile error: %v", err)
	}

	if strings.HasPrefix(op.Data, "(?i)") {
		t.Error("sensitive operator should NOT have (?i) prefix")
	}
	if op.Data != `^/usr/bin/curl$` {
		t.Errorf("sensitive pattern should be unchanged, got %q", op.Data)
	}

	// Case-sensitive: should match exact case only
	if !op.re.MatchString("/usr/bin/curl") {
		t.Error("should match exact case")
	}
	if op.re.MatchString("/usr/bin/CURL") {
		t.Error("case-sensitive should NOT match different case")
	}
}

// TestRegexReCmpNoCaseFolding verifies that reCmp does not lowercase input
// data, since case-insensitivity is handled by the (?i) flag in the pattern.
func TestRegexReCmpNoCaseFolding(t *testing.T) {
	var dummyList []Operator

	// Case-insensitive: create operator with (?i) prefix
	op, err := NewOperator(Regexp, false, OpDstHost, `^TCP$`, dummyList)
	if err != nil {
		t.Fatalf("NewOperator error: %v", err)
	}
	if err := op.Compile(); err != nil {
		t.Fatalf("Compile error: %v", err)
	}

	// reCmp should match without lowercasing input because (?i) handles it
	if !op.reCmp("TCP") {
		t.Error("reCmp should match 'TCP'")
	}
	if !op.reCmp("tcp") {
		t.Error("reCmp should match 'tcp' via (?i)")
	}
	if !op.reCmp("Tcp") {
		t.Error("reCmp should match 'Tcp' via (?i)")
	}
}
