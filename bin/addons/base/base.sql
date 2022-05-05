-------------------------------------------------------------------------
-- Pure SQL
-------------------------------------------------------------------------

-------------------------------------------------------------------------
-- IR dictionary
-------------------------------------------------------------------------

create table ir_values
(
    id bigserial,
    name varchar(128) not null,
    key varchar(128) not null,
    key2 varchar(256) not null,
    model varchar(128) not null,
    value text,
    meta text default NULL,
    res_id bigint default null,
    primary key (id)
);

-------------------------------------------------------------------------
-- Modules Description
-------------------------------------------------------------------------

CREATE TABLE ir_model (
  id bigserial,
  model varchar(64) DEFAULT ''::varchar NOT NULL,
  name varchar(64),
  state varchar(16),
  info text,
  primary key(id)
);

CREATE TABLE ir_model_fields (
  id bigserial,
  model varchar(64) DEFAULT ''::varchar NOT NULL,
  model_id bigint references ir_model on delete cascade,
  name varchar(64) DEFAULT ''::varchar NOT NULL,
  relation varchar(64),
  select_level varchar(4),
  field_description varchar(256),
  ttype varchar(64),
  state varchar(64) default 'base',
  view_load boolean,
  relate boolean default False,
  relation_field varchar(128),
  translate boolean default False,
  primary key(id)
);


-------------------------------------------------------------------------
-- Actions
-------------------------------------------------------------------------

CREATE TABLE ir_actions (
    id bigserial NOT NULL,
    name varchar(64) DEFAULT ''::varchar NOT NULL,
    "type" varchar(32) DEFAULT 'window'::varchar NOT NULL,
    usage varchar(32) DEFAULT null,
    primary key(id)
);

CREATE TABLE ir_act_window (
    view_id bigint,
    res_model varchar(64),
    view_type varchar(16),
    "domain" varchar(250),
    primary key(id)
)
INHERITS (ir_actions);

CREATE TABLE ir_act_report_xml (
    model varchar(64) NOT NULL,
    report_name varchar(64) NOT NULL,
    report_xsl varchar(256),
    report_xml varchar(256),
    auto boolean default true,
    primary key(id)
)
INHERITS (ir_actions);

create table ir_act_report_custom (
    report_id bigint,
--  report_id bigint references ir_report_custom
    primary key(id)
)
INHERITS (ir_actions);

CREATE TABLE ir_act_wizard (
    wiz_name varchar(64) NOT NULL,
    primary key(id)
)
INHERITS (ir_actions);

CREATE TABLE ir_act_url (
    url text NOT NULL,
    target varchar(64) NOT NULL,
    primary key(id)
)
INHERITS (ir_actions);

CREATE TABLE ir_act_server (
    primary key(id)
)
INHERITS (ir_actions);


CREATE TABLE ir_ui_view (
    id bigserial NOT NULL,
    name varchar(64) DEFAULT ''::varchar NOT NULL,
    model varchar(64) DEFAULT ''::varchar NOT NULL,
    "type" varchar(64) DEFAULT 'form'::varchar NOT NULL,
    arch text NOT NULL,
    field_parent varchar(64),
    priority integer DEFAULT 5 NOT NULL,
    primary key(id)
);

CREATE TABLE ir_ui_menu (
    id bigserial NOT NULL,
    parent_id bigint references ir_ui_menu on delete set null,
    name varchar(64) DEFAULT ''::varchar NOT NULL,
    icon varchar(64) DEFAULT ''::varchar,
    primary key (id)
);

select setval('ir_ui_menu_id_seq', 2);

---------------------------------
-- Res users
---------------------------------

-- level:
--   0  RESTRICT TO USER
--   1  RESTRICT TO GROUP
--   2  PUBLIC

CREATE TABLE res_users (
    id bigserial NOT NULL,
    name varchar(64) not null,
    active boolean default True,
    login varchar(64) NOT NULL UNIQUE,
    password varchar(64) default null,
    email varchar(64) default null,
    context_tz varchar(64) default null,
    signature text,
    context_lang varchar(64) default '',
    -- No FK references below, will be added later by ORM
    -- (when the destination rows exist)
    company_id bigint,
    primary key(id)
);
alter table res_users add constraint res_users_login_uniq unique (login);

CREATE TABLE res_groups (
    id bigserial NOT NULL,
    name varchar(64) NOT NULL,
    primary key(id)
);

CREATE TABLE res_groups_users_rel (
    uid bigint NOT NULL references res_users on delete cascade,
    gid bigint NOT NULL references res_groups on delete cascade,
    UNIQUE("uid","gid")
);

create index res_groups_users_rel_uid_idx on res_groups_users_rel (uid);
create index res_groups_users_rel_gid_idx on res_groups_users_rel (gid);


---------------------------------
-- Workflows
---------------------------------

create table wkf
(
    id bigserial,
    name varchar(64),
    osv varchar(64),
    on_create bool default False,
    primary key(id)
);

create table wkf_activity
(
    id bigserial,
    wkf_id bigint references wkf on delete cascade,
    subflow_id bigint references wkf on delete set null,
    split_mode varchar(3) default 'XOR',
    join_mode varchar(3) default 'XOR',
    kind varchar(16) not null default 'dummy',
    name varchar(64),
    signal_send varchar(32) default null,
    flow_start boolean default False,
    flow_stop boolean default False,
    action text default null,
    primary key(id)
);

create table wkf_transition
(
    id bigserial,
    act_from bigint references wkf_activity on delete cascade,
    act_to bigint references wkf_activity on delete cascade,
    condition varchar(128) default NULL,

    trigger_type varchar(128) default NULL,
    trigger_expr_id varchar(128) default NULL,

    signal varchar(64) default null,
    group_id bigint references res_groups on delete set null,

    primary key(id)
);

create table wkf_instance
(
    id bigserial,
    wkf_id bigint references wkf on delete restrict,
    uid bigint default null,
    res_id bigint not null,
    res_type varchar(64) not null,
    state varchar(32) not null default 'active',
    primary key(id)
);

create table wkf_workitem
(
    id bigserial,
    act_id bigint not null references wkf_activity on delete cascade,
    inst_id bigint not null references wkf_instance on delete cascade,
    subflow_id bigint references wkf_instance on delete cascade,
    state varchar(64) default 'blocked',
    primary key(id)
);

create table wkf_witm_trans
(
    trans_id bigint not null references wkf_transition on delete cascade,
    inst_id bigint not null references wkf_instance on delete cascade
);

create index wkf_witm_trans_inst_idx on wkf_witm_trans (inst_id);

create table wkf_logs
(
    id bigserial,
    res_type varchar(128) not null,
    res_id bigint not null,
    uid bigint references res_users on delete set null,
    act_id bigint references wkf_activity on delete set null,
    time time not null,
    info varchar(128) default NULL,
    primary key(id)
);

---------------------------------
-- Modules
---------------------------------

CREATE TABLE ir_module_category (
    id bigserial NOT NULL,
    create_uid bigint references res_users on delete set null,
    create_date timestamp without time zone,
    write_date timestamp without time zone,
    write_uid bigint references res_users on delete set null,
    parent_id bigint REFERENCES ir_module_category ON DELETE SET NULL,
    name character varying(128) NOT NULL,
    primary key(id)
);


CREATE TABLE ir_module_module (
    id bigserial NOT NULL,
    create_uid bigint references res_users on delete set null,
    create_date timestamp without time zone,
    write_date timestamp without time zone,
    write_uid bigint references res_users on delete set null,
    website character varying(256),
    name character varying(128) NOT NULL,
    author character varying(128),
    url character varying(128),
    state character varying(16),
    latest_version character varying(64),
    shortdesc character varying(256),
    category_id bigint REFERENCES ir_module_category ON DELETE SET NULL,
    certificate character varying(64),
    description text,
    demo boolean default False,
    web boolean DEFAULT FALSE,
    license character varying(32),
    primary key(id)
);
ALTER TABLE ir_module_module add constraint name_uniq unique (name);

CREATE TABLE ir_module_module_dependency (
    id bigserial NOT NULL,
    create_uid bigint references res_users on delete set null,
    create_date timestamp without time zone,
    write_date timestamp without time zone,
    write_uid bigint references res_users on delete set null,
    name character varying(128),
    version_pattern character varying(128) default NULL,
    module_id bigint REFERENCES ir_module_module ON DELETE cascade,
    primary key(id)
);

CREATE TABLE res_company (
    id bigserial NOT NULL,
    name character varying(64) not null,
    parent_id bigint references res_company on delete set null,
    primary key(id)
);

CREATE TABLE ir_model_data (
    id bigserial NOT NULL,
    create_uid bigint,
    create_date timestamp without time zone,
    write_date timestamp without time zone,
    write_uid bigint,
    noupdate boolean,
    name character varying(128) NOT NULL,
    date_init timestamp without time zone,
    date_update timestamp without time zone,
    module character varying(64) NOT NULL,
    model character varying(64) NOT NULL,
    res_id bigint, primary key(id)
);

---------------------------------
-- Users
---------------------------------

insert into res_users (id,login,password,name,active,company_id,context_lang) values (1,'admin','admin','Administrator',True,1,'en_US');
insert into ir_model_data (name,module,model,noupdate,res_id) values ('user_root','base','res.users',True,1);

-- Compatibility purpose, to remove V6.0
insert into ir_model_data (name,module,model,noupdate,res_id) values ('user_admin','base','res.users',True,1);

select setval('res_users_id_seq', 2);
