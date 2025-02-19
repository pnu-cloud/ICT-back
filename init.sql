DROP TABLE IF EXISTS "user";

CREATE TABLE "user" (
	"id"	serial	NOT NULL,
	"email"	varchar(255)	NULL,
	"password"	varchar(255)	NULL,
	"name"	varchar(255)	NULL
);

DROP TABLE IF EXISTS "subject";

CREATE TABLE "subject" (
	"id"	serial	NOT NULL,
	"user_id"	integer	NOT NULL,
	"title"	varchar(255)	NULL,
	"text"	text	NULL,
    "progress" integer DEFAULT 0
);

DROP TABLE IF EXISTS "chapter";

CREATE TABLE "chapter" (
	"id"	serial	NOT NULL,
	"subject_id"	serial	NOT NULL,
	"title"	varchar(255)	NULL,
	"content"	text	NULL
);

DROP TABLE IF EXISTS "problem";

CREATE TABLE "problem" (
	"id"	serial	NOT NULL,
	"quiz_id"	integer	NOT NULL,
	"title"	text	NULL,
	"question"	text	NULL,
	"feedback"	text	NULL,
	"solution"	text	NULL,
	"user_answer"	text	NULL,
	"is_correct"	boolean	NULL
);

DROP TABLE IF EXISTS "quiz";

CREATE TABLE "quiz" (
	"id"	serial	NOT NULL,
	"chapter_id"	integer	NOT NULL,
	"total_count"	integer	NULL,
	"submit_count"	integer	NULL,
	"correct_count"	integer	NULL
);

ALTER TABLE "user" ADD CONSTRAINT "PK_USER" PRIMARY KEY (
	"id"
);

ALTER TABLE "subject" ADD CONSTRAINT "PK_SUBJECT" PRIMARY KEY (
	"id"
);

ALTER TABLE "chapter" ADD CONSTRAINT "PK_CHAPTER" PRIMARY KEY (
	"id"
);

ALTER TABLE "problem" ADD CONSTRAINT "PK_PROBLEM" PRIMARY KEY (
	"id"
);

ALTER TABLE "quiz" ADD CONSTRAINT "PK_QUIZ" PRIMARY KEY (
	"id"
);
