--
-- PostgreSQL database dump
--

\restrict TG4XQKZWxFJ4CpJ686AcThKFggD8xhYAFcBBrCsHEF1CdbcJeMmPsEgkLBVYnEP

-- Dumped from database version 15.17
-- Dumped by pg_dump version 15.17

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: fisher_angler_profiles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_angler_profiles (
    id integer NOT NULL,
    player_id integer NOT NULL,
    avatar_url text DEFAULT ''::text,
    bio character varying(512) DEFAULT ''::character varying,
    real_name character varying(64) DEFAULT ''::character varying,
    city character varying(64) DEFAULT ''::character varying,
    years_fishing integer DEFAULT 0,
    favorite_target character varying(64) DEFAULT ''::character varying,
    gear_list character varying(512) DEFAULT ''::character varying,
    is_vip boolean DEFAULT false,
    vip_since double precision,
    total_real_catches integer DEFAULT 0,
    total_likes integer DEFAULT 0,
    created_at double precision
);


--
-- Name: fisher_angler_profiles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_angler_profiles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_angler_profiles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_angler_profiles_id_seq OWNED BY public.fisher_angler_profiles.id;


--
-- Name: fisher_asset_showcase; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_asset_showcase (
    id integer NOT NULL,
    player_id integer NOT NULL,
    asset_type character varying(32) DEFAULT ''::character varying,
    name character varying(128) DEFAULT ''::character varying,
    description character varying(512) DEFAULT ''::character varying,
    photo_url text DEFAULT ''::text,
    price_value integer DEFAULT 0,
    is_verified boolean DEFAULT false,
    created_at double precision
);


--
-- Name: fisher_asset_showcase_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_asset_showcase_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_asset_showcase_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_asset_showcase_id_seq OWNED BY public.fisher_asset_showcase.id;


--
-- Name: fisher_assets; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_assets (
    id integer NOT NULL,
    owner_id integer NOT NULL,
    asset_type character varying(16),
    name character varying(64) DEFAULT ''::character varying,
    level integer DEFAULT 1,
    income_bonus_pct integer DEFAULT 5,
    purchase_price integer DEFAULT 1000,
    purchased_at double precision
);


--
-- Name: fisher_assets_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_assets_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_assets_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_assets_id_seq OWNED BY public.fisher_assets.id;


--
-- Name: fisher_audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_audit_log (
    id integer NOT NULL,
    player_id integer,
    action character varying(64),
    detail character varying(256),
    ip character varying(64),
    created_at double precision
);


--
-- Name: fisher_audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_audit_log_id_seq OWNED BY public.fisher_audit_log.id;


--
-- Name: fisher_bottles; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_bottles (
    id integer NOT NULL,
    thrower_id integer NOT NULL,
    picker_id integer,
    message character varying(256) DEFAULT ''::character varying,
    reply character varying(256) DEFAULT ''::character varying,
    status character varying(16) DEFAULT 'floating'::character varying,
    thrown_at double precision,
    picked_at double precision
);


--
-- Name: fisher_bottles_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_bottles_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_bottles_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_bottles_id_seq OWNED BY public.fisher_bottles.id;


--
-- Name: fisher_catch_gallery; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_catch_gallery (
    id integer NOT NULL,
    player_id integer NOT NULL,
    species character varying(64) DEFAULT ''::character varying,
    weight_kg double precision DEFAULT 0,
    location character varying(128) DEFAULT ''::character varying,
    photo_url text DEFAULT ''::text,
    story text DEFAULT ''::text,
    likes integer DEFAULT 0,
    comments_json text DEFAULT '[]'::text,
    created_at double precision,
    video_url character varying(512) DEFAULT ''::character varying
);


--
-- Name: fisher_catch_gallery_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_catch_gallery_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_catch_gallery_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_catch_gallery_id_seq OWNED BY public.fisher_catch_gallery.id;


--
-- Name: fisher_club_members; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_club_members (
    id integer NOT NULL,
    club_id integer NOT NULL,
    player_id integer NOT NULL,
    role character varying(16) DEFAULT 'member'::character varying,
    joined_at double precision
);


--
-- Name: fisher_club_members_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_club_members_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_club_members_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_club_members_id_seq OWNED BY public.fisher_club_members.id;


--
-- Name: fisher_clubs; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_clubs (
    id integer NOT NULL,
    name character varying(64) NOT NULL,
    description character varying(256) DEFAULT ''::character varying,
    creator_id integer NOT NULL,
    member_count integer DEFAULT 1,
    location character varying(128) DEFAULT ''::character varying,
    created_at double precision
);


--
-- Name: fisher_clubs_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_clubs_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_clubs_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_clubs_id_seq OWNED BY public.fisher_clubs.id;


--
-- Name: fisher_diaries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_diaries (
    id integer NOT NULL,
    player_id integer NOT NULL,
    title character varying(128) DEFAULT ''::character varying,
    content text DEFAULT ''::text,
    location character varying(128) DEFAULT ''::character varying,
    weather character varying(32) DEFAULT ''::character varying,
    photos_json text DEFAULT '[]'::text,
    likes integer DEFAULT 0,
    created_at double precision,
    video_url character varying(512) DEFAULT ''::character varying
);


--
-- Name: fisher_diaries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_diaries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_diaries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_diaries_id_seq OWNED BY public.fisher_diaries.id;


--
-- Name: fisher_fisheries; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_fisheries (
    id integer NOT NULL,
    owner_id integer NOT NULL,
    name character varying(64) DEFAULT ''::character varying,
    land_type character varying(16) DEFAULT 'pond'::character varying,
    level integer DEFAULT 1,
    income_per_hour integer DEFAULT 5,
    upgrade_cost_coins integer DEFAULT 500,
    workers_max integer DEFAULT 3,
    created_at double precision
);


--
-- Name: fisher_fisheries_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_fisheries_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_fisheries_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_fisheries_id_seq OWNED BY public.fisher_fisheries.id;


--
-- Name: fisher_orders; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_orders (
    id integer NOT NULL,
    seller_id integer NOT NULL,
    buyer_id integer,
    species_id integer NOT NULL,
    species_name character varying(32) DEFAULT ''::character varying,
    order_type character varying(8) DEFAULT 'sell'::character varying,
    quantity integer DEFAULT 1,
    price_per_unit integer DEFAULT 1,
    total_price integer DEFAULT 0,
    status character varying(16) DEFAULT 'active'::character varying,
    created_at double precision,
    filled_at double precision
);


--
-- Name: fisher_orders_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_orders_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_orders_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_orders_id_seq OWNED BY public.fisher_orders.id;


--
-- Name: fisher_players; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_players (
    id integer NOT NULL,
    dev_key character varying(128),
    openid character varying(64),
    nickname character varying(64) DEFAULT ''::character varying NOT NULL,
    coins integer DEFAULT 100 NOT NULL,
    score integer DEFAULT 0 NOT NULL,
    rod_level integer DEFAULT 0 NOT NULL,
    spot_id integer DEFAULT 0 NOT NULL,
    inventory_json text DEFAULT '{}'::text NOT NULL,
    last_cast_at double precision,
    equipment_json text DEFAULT '{}'::text
);


--
-- Name: fisher_players_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_players_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_players_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_players_id_seq OWNED BY public.fisher_players.id;


--
-- Name: fisher_real_catches; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_real_catches (
    id integer NOT NULL,
    player_id integer NOT NULL,
    image_data text DEFAULT ''::text,
    species_guess character varying(64) DEFAULT ''::character varying,
    weight_kg double precision DEFAULT 0,
    location_desc character varying(128) DEFAULT ''::character varying,
    verified boolean DEFAULT false,
    coin_reward integer DEFAULT 0,
    caught_at double precision
);


--
-- Name: fisher_real_catches_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_real_catches_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_real_catches_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_real_catches_id_seq OWNED BY public.fisher_real_catches.id;


--
-- Name: fisher_species; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_species (
    id integer NOT NULL,
    name character varying(32) NOT NULL,
    price integer NOT NULL,
    currency character varying(8) NOT NULL,
    spot_id integer NOT NULL,
    rarity character varying(16) NOT NULL,
    description character varying(256) NOT NULL,
    min_rod_level integer NOT NULL,
    weight_min double precision NOT NULL,
    weight_max double precision NOT NULL
);


--
-- Name: fisher_species_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_species_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_species_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_species_id_seq OWNED BY public.fisher_species.id;


--
-- Name: fisher_spots; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_spots (
    id integer NOT NULL,
    name character varying(32) NOT NULL,
    unlock_coins integer NOT NULL,
    unlock_score integer NOT NULL,
    unlock_rod_level integer NOT NULL,
    description character varying(256) NOT NULL,
    sort_order integer NOT NULL
);


--
-- Name: fisher_spots_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_spots_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_spots_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_spots_id_seq OWNED BY public.fisher_spots.id;


--
-- Name: fisher_workers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.fisher_workers (
    id integer NOT NULL,
    fishery_id integer NOT NULL,
    name character varying(32) DEFAULT '渔工'::character varying,
    skill_level integer DEFAULT 1,
    catch_rate integer DEFAULT 3,
    salary_per_hour integer DEFAULT 2,
    hired_at double precision
);


--
-- Name: fisher_workers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.fisher_workers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: fisher_workers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.fisher_workers_id_seq OWNED BY public.fisher_workers.id;


--
-- Name: fisher_angler_profiles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_angler_profiles ALTER COLUMN id SET DEFAULT nextval('public.fisher_angler_profiles_id_seq'::regclass);


--
-- Name: fisher_asset_showcase id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_asset_showcase ALTER COLUMN id SET DEFAULT nextval('public.fisher_asset_showcase_id_seq'::regclass);


--
-- Name: fisher_assets id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_assets ALTER COLUMN id SET DEFAULT nextval('public.fisher_assets_id_seq'::regclass);


--
-- Name: fisher_audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_audit_log ALTER COLUMN id SET DEFAULT nextval('public.fisher_audit_log_id_seq'::regclass);


--
-- Name: fisher_bottles id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_bottles ALTER COLUMN id SET DEFAULT nextval('public.fisher_bottles_id_seq'::regclass);


--
-- Name: fisher_catch_gallery id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_catch_gallery ALTER COLUMN id SET DEFAULT nextval('public.fisher_catch_gallery_id_seq'::regclass);


--
-- Name: fisher_club_members id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_club_members ALTER COLUMN id SET DEFAULT nextval('public.fisher_club_members_id_seq'::regclass);


--
-- Name: fisher_clubs id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_clubs ALTER COLUMN id SET DEFAULT nextval('public.fisher_clubs_id_seq'::regclass);


--
-- Name: fisher_diaries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_diaries ALTER COLUMN id SET DEFAULT nextval('public.fisher_diaries_id_seq'::regclass);


--
-- Name: fisher_fisheries id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_fisheries ALTER COLUMN id SET DEFAULT nextval('public.fisher_fisheries_id_seq'::regclass);


--
-- Name: fisher_orders id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_orders ALTER COLUMN id SET DEFAULT nextval('public.fisher_orders_id_seq'::regclass);


--
-- Name: fisher_players id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_players ALTER COLUMN id SET DEFAULT nextval('public.fisher_players_id_seq'::regclass);


--
-- Name: fisher_real_catches id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_real_catches ALTER COLUMN id SET DEFAULT nextval('public.fisher_real_catches_id_seq'::regclass);


--
-- Name: fisher_species id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_species ALTER COLUMN id SET DEFAULT nextval('public.fisher_species_id_seq'::regclass);


--
-- Name: fisher_spots id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_spots ALTER COLUMN id SET DEFAULT nextval('public.fisher_spots_id_seq'::regclass);


--
-- Name: fisher_workers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_workers ALTER COLUMN id SET DEFAULT nextval('public.fisher_workers_id_seq'::regclass);


--
-- Data for Name: fisher_angler_profiles; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_angler_profiles (id, player_id, avatar_url, bio, real_name, city, years_fishing, favorite_target, gear_list, is_vip, vip_since, total_real_catches, total_likes, created_at) FROM stdin;
1	30		海钓达人			0			f	\N	1	0	1778685915.5585515
2	36		测试			0			f	\N	0	0	1778721337.2322578
\.


--
-- Data for Name: fisher_asset_showcase; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_asset_showcase (id, player_id, asset_type, name, description, photo_url, price_value, is_verified, created_at) FROM stdin;
\.


--
-- Data for Name: fisher_assets; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_assets (id, owner_id, asset_type, name, level, income_bonus_pct, purchase_price, purchased_at) FROM stdin;
\.


--
-- Data for Name: fisher_audit_log; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_audit_log (id, player_id, action, detail, ip, created_at) FROM stdin;
\.


--
-- Data for Name: fisher_bottles; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_bottles (id, thrower_id, picker_id, message, reply, status, thrown_at, picked_at) FROM stdin;
1	17	18	有人吗？一起钓鱼啊！		picked	1778683819.591949	1778683819.6158788
2	31	10	今天天气真好！	遇见你真好，一起钓鱼吧！🐟	replied	1778686625.3617406	1778687617.5820608
3	33	34	一起钓鱼吧!		picked	1778689425.7081962	1778689425.751225
4	10	\N	今天钓到一条大鱼！🐟		floating	1778689557.7977245	\N
8	1	\N	今天的海浪很温柔 🌊		floating	1778690084.8975217	\N
9	1	\N	有人一起出海钓鱼吗？		floating	1778690084.8990273	\N
11	1	\N	这里风景真美		floating	1778690084.9000976	\N
12	1	\N	想找个钓友一起玩		floating	1778690084.900589	\N
6	10	35	今天钓到一条大鱼！🐟		picked	1778689954.7247252	1778690106.5236309
5	10	10	今天钓到一条大鱼！🐟	遇见你真好，一起钓鱼吧！🐟	replied	1778689797.286815	1778690253.6216776
10	1	10	昨天钓到一条大石斑！		picked	1778690084.8995802	1778690501.9338899
\.


--
-- Data for Name: fisher_catch_gallery; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_catch_gallery (id, player_id, species, weight_kg, location, photo_url, story, likes, comments_json, created_at, video_url) FROM stdin;
1	30	东星斑	8.5	西沙			0	[]	1778685915.6509233	
\.


--
-- Data for Name: fisher_club_members; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_club_members (id, club_id, player_id, role, joined_at) FROM stdin;
1	1	21	creator	1778684854.6033378
\.


--
-- Data for Name: fisher_clubs; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_clubs (id, name, description, creator_id, member_count, location, created_at) FROM stdin;
1	杭州西湖垂钓团		21	1	杭州	1778684854.5991004
\.


--
-- Data for Name: fisher_diaries; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_diaries (id, player_id, title, content, location, weather, photos_json, likes, created_at, video_url) FROM stdin;
\.


--
-- Data for Name: fisher_fisheries; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_fisheries (id, owner_id, name, land_type, level, income_per_hour, upgrade_cost_coins, workers_max, created_at) FROM stdin;
\.


--
-- Data for Name: fisher_orders; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_orders (id, seller_id, buyer_id, species_id, species_name, order_type, quantity, price_per_unit, total_price, status, created_at, filled_at) FROM stdin;
\.


--
-- Data for Name: fisher_players; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_players (id, dev_key, openid, nickname, coins, score, rod_level, spot_id, inventory_json, last_cast_at, equipment_json) FROM stdin;
1	test-user-001	\N		100	0	0	0	{"3":1}	1778425591.4548635	{}
2	web-test	\N		100	0	0	0	{"3":1}	1778426188.9622142	{}
10	user_h82mb648	\N		288	0	2	0	{"2":2,"4":2,"3":1}	1779203109.995813	{"bait":{"name":"鱼饵","durability":20,"max_durability":20}}
4	test99	\N		50	0	1	0	{}	\N	{}
5	buytest	\N		50	0	0	0	{}	\N	{"bait":{"name":"鱼饵","durability":20,"max_durability":20}}
6	eq-test	\N		100	0	0	0	{}	\N	{}
7	eq-test2	\N		50	0	0	0	{}	\N	{"bait":{"name":"鱼饵","durability":20,"max_durability":20}}
8	debug-test	\N		50	0	0	0	{}	\N	{"bait":{"name":"鱼饵","durability":20,"max_durability":20}}
9	final-test	\N		50	0	0	0	{}	\N	{"bait":{"name":"鱼饵","durability":20,"max_durability":20}}
3	default-player	\N		100	0	0	1	{"4":1,"8":3}	1778428636.0369134	{}
15	e2e-test-001	\N		0	0	1	0	{"2":1}	1778682781.4040673	{"bait":{"name":"鱼饵","durability":20,"max_durability":20}}
11	polish-test	\N		50	0	1	0	{"5":1}	1778430589.9246275	{}
16	bottle-test	\N		100	0	0	0	{}	\N	{}
17	b2	\N		100	0	0	0	{}	\N	{}
18	b3	\N		100	0	0	0	{}	\N	{}
19	lb-test	\N		100	0	0	0	{}	\N	{}
20	club-test2	\N		100	0	0	0	{}	\N	{}
21	py-club	\N		105	1	0	0	{}	\N	{}
22	show-test	\N		100	0	0	0	{}	\N	{}
23	quick	\N		100	0	0	0	{}	\N	{}
24	show2	\N		100	0	0	0	{}	\N	{}
25	show4	\N		100	0	0	0	{}	\N	{}
26	show5	\N		100	0	0	0	{}	\N	{}
27	show6	\N		100	0	0	0	{}	\N	{}
12	tycoon-test	\N		100	0	0	0	{}	\N	{}
28	show7	\N		100	0	0	0	{}	\N	{}
13	market-test	\N		100	0	0	0	{"5":1,"4":1}	1778478355.72223	{}
14	mkt-fix	\N		100	0	0	0	{"5":1}	1778478377.3960638	{}
29	s-final	\N		100	0	0	0	{}	\N	{}
30	done	\N		100	0	0	0	{}	\N	{}
31	safety	\N		110	0	0	0	{}	\N	{}
32	check-404	\N		100	0	0	0	{}	\N	{}
33	fix1	\N		100	0	0	0	{}	\N	{}
34	fix2	\N		100	0	0	0	{}	\N	{}
35	b-test	\N		100	0	0	0	{}	\N	{}
36	verify	\N		100	0	0	0	{}	\N	{}
\.


--
-- Data for Name: fisher_real_catches; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_real_catches (id, player_id, image_data, species_guess, weight_kg, location_desc, verified, coin_reward, caught_at) FROM stdin;
1	21		鲫鱼	1.2	西湖	t	5	1778684854.6131945
\.


--
-- Data for Name: fisher_species; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_species (id, name, price, currency, spot_id, rarity, description, min_rod_level, weight_min, weight_max) FROM stdin;
1	白条	8	coin	0	common	最常见的小杂鱼，油炸很香。	0	0.02	0.15
2	小鲫鱼	12	coin	0	common	乡间小河的特产，熬汤鲜美。	0	0.05	0.3
3	麦穗鱼	10	coin	0	common	身形细长如麦穗，成群结队。	0	0.01	0.08
4	塘鳢	20	coin	0	uncommon	趴在石头底下的懒家伙。	0	0.05	0.25
5	河鳗	35	coin	0	rare	滑溜溜的夜行者，力气不小。	0	0.3	1.5
6	金色小鲫	55	coin	0	epic	罕见的金色变种，传说能带来好运。	0	0.2	0.6
7	小鲤鱼	18	coin	1	common	鲤鱼跃龙门的幼年版。	0	0.1	0.8
8	罗非鱼	22	coin	1	common	来自非洲的入侵者，繁殖力惊人。	0	0.15	0.6
9	泥鳅	15	coin	1	common	淤泥里的小泥鳅，滑不溜手。	0	0.02	0.1
10	黄颡鱼	28	coin	1	uncommon	嘎牙子，背鳍有毒刺，小心摘钩。	0	0.1	0.5
11	鳜鱼	45	coin	1	rare	桃花流水鳜鱼肥，淡水鱼中的贵族。	0	0.3	2
12	锦鲤王	80	coin	1	epic	身披彩鳞的池中王者。	0	1.5	5
13	草鱼	35	coin	2	common	吃草的巨物，上钩后力道十足。	0	0.5	3
14	青鱼	48	coin	2	uncommon	湖底的石螺杀手，体长可达一米。	0	1	8
15	鲢鱼	30	coin	2	common	滤食浮游生物，净化水质的好帮手。	0	0.5	2.5
16	鳙鱼	38	coin	2	uncommon	大头鱼，剁椒鱼头的主角。	0	1	5
17	甲鱼	70	coin	2	rare	不是鱼，是鳖！大补之物。	0	0.5	3
18	湖中巨鲤	120	score	2	epic	传说活了上百年的老鲤，鳞片如铜钱大小。	0	5	15
19	黑鱼	55	coin	3	uncommon	凶猛的掠食者，牙齿锋利。	0	1	5
20	鲶鱼	52	coin	3	uncommon	江底的夜行巨兽，两根长须如鞭。	0	0.8	6
21	巨型鲤鱼	68	coin	3	uncommon	江中力道十足的搏斗者。	0	2	10
22	鳡鱼	85	coin	3	rare	淡水鲨鱼！时速可达60公里。	0	3	15
23	鲟鱼	150	score	3	rare	活化石，鱼子酱来自它的后代。	0	5	30
24	江豚	300	score	3	legendary	长江的微笑天使…你不会真的钓它吧？拍照放生后获得大量积分。	0	30	80
25	小黄鱼	2	score	4	common	金黄的小家伙，香煎最好吃。	0	0.05	0.3
26	带鱼	3	score	4	common	银光闪闪的带子，离开水面就死。	0	0.3	1.5
27	海鲈	5	score	4	uncommon	海钓入门的最佳目标鱼。	0	1	5
28	鲷鱼	6	score	4	uncommon	真鲷，红色喜庆，刺身极品。	0	0.5	3
29	石斑鱼	10	score	4	rare	礁石区的霸王，清蒸一绝。	0	2	15
30	变异浅海巨鱼	12	score	4	rare	核废水造就的怪物？还是深海逃上来的异兽？	0	10	50
31	荧光水母鱼	8	score	5	common	透明身体发出幽幽蓝光，像游动的小灯泡。	0	0.01	0.2
32	盲眼洞穴鱼	10	score	5	common	没有眼睛，靠侧线感知一切。	0	0.05	0.3
33	石甲鲶	15	score	5	uncommon	皮肤硬如岩石，在暗河中擦身而过。	0	0.5	3
34	电鳗	20	score	5	uncommon	别碰！800伏特高压，瞬间麻痹。	0	1	8
35	暗河巨骨舌鱼	35	score	5	rare	亚马逊的远古巨鱼，不知如何出现在这里。	0	20	100
36	幽灵水母王	60	score	5	epic	千年水母王，触手可延伸数十米。	0	0.5	5
37	深渊巨口	100	score	5	legendary	暗河最深处的传说，张开的大嘴能吞下一艘小船。	0	50	200
38	灯笼鱼	12	score	6	common	头顶发光器，深海中的点点星光。	0	0.05	0.5
39	深海鳕鱼	15	score	6	common	冷冽深海中的肥美鱼生。	0	0.5	3
40	龙宫侍女锦鲤	25	score	6	uncommon	身披七彩鳞片，据说是龙宫侍女的化身。	0	2	8
41	龟丞相	40	score	6	rare	背甲上刻着古老文字的大海龟。	0	10	50
42	深海鮟鱇	45	score	6	rare	丑到极致就是美，深海猎手。	0	5	30
43	龙王幼子	80	score	6	epic	身披金鳞的小龙，角刚冒出头顶。	0	30	150
44	深海龙鱼	150	score	6	legendary	龙宫深渊的主人，鳞片比盔甲还硬，一口龙息可蒸干浅海。	0	100	500
45	三叶虫	20	score	7	common	寒武纪的活化石，居然上了钩！	0	0.01	0.1
46	菊石	30	score	7	uncommon	螺旋外壳的远古头足类，触手依然在蠕动。	0	0.5	5
47	邓氏鱼	50	score	7	rare	泥盆纪的海洋霸主，咬合力数吨！	0	50	200
48	巨齿鲨	80	score	7	epic	史上最强掠食者，一颗牙比手掌还大。	0	1000	5000
49	利维坦鲸	120	score	7	epic	远古巨鲸，与巨齿鲨争夺海洋霸权。	0	3000	10000
50	远古海神	300	score	7	legendary	时间尽头的终极存在，钓上它的人将成为新的传说。	0	10000	50000
\.


--
-- Data for Name: fisher_spots; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_spots (id, name, unlock_coins, unlock_score, unlock_rod_level, description, sort_order) FROM stdin;
0	乡村小河	0	0	0	家门口的小河沟，水流平缓，适合新手练手。	0
1	野外池塘	0	0	0	绿树环绕的野塘，水草丛生，暗藏好货。	1
2	郊外湖泊	300	0	0	晨雾缭绕的大湖，鱼种丰富，是进阶钓手的天堂。	2
3	沿江堤坝	800	0	2	江水奔腾，暗流涌动，只有老手才敢下竿。	3
4	近海码头	1500	0	5	咸腥的海风扑面，远处白帆点点，该征服大海了。	4
5	秘境暗流	3000	200	8	传说中的地下暗河，荧光水母照亮幽深水域，栖息着远古异种。	5
6	龙宫深渊	6000	500	12	深海裂谷万丈之下，龙宫的残垣散落海底，传说之鱼在此巡游。	6
7	远古海域	12000	1000	18	时间尽头的原始海洋，巨兽横行，只有最顶尖的钓者才敢踏足。	7
\.


--
-- Data for Name: fisher_workers; Type: TABLE DATA; Schema: public; Owner: -
--

COPY public.fisher_workers (id, fishery_id, name, skill_level, catch_rate, salary_per_hour, hired_at) FROM stdin;
\.


--
-- Name: fisher_angler_profiles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_angler_profiles_id_seq', 2, true);


--
-- Name: fisher_asset_showcase_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_asset_showcase_id_seq', 1, false);


--
-- Name: fisher_assets_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_assets_id_seq', 1, false);


--
-- Name: fisher_audit_log_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_audit_log_id_seq', 1, false);


--
-- Name: fisher_bottles_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_bottles_id_seq', 12, true);


--
-- Name: fisher_catch_gallery_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_catch_gallery_id_seq', 1, true);


--
-- Name: fisher_club_members_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_club_members_id_seq', 1, true);


--
-- Name: fisher_clubs_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_clubs_id_seq', 1, true);


--
-- Name: fisher_diaries_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_diaries_id_seq', 1, false);


--
-- Name: fisher_fisheries_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_fisheries_id_seq', 1, false);


--
-- Name: fisher_orders_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_orders_id_seq', 1, false);


--
-- Name: fisher_players_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_players_id_seq', 36, true);


--
-- Name: fisher_real_catches_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_real_catches_id_seq', 1, true);


--
-- Name: fisher_species_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_species_id_seq', 1, false);


--
-- Name: fisher_spots_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_spots_id_seq', 1, false);


--
-- Name: fisher_workers_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.fisher_workers_id_seq', 1, false);


--
-- Name: fisher_angler_profiles fisher_angler_profiles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_angler_profiles
    ADD CONSTRAINT fisher_angler_profiles_pkey PRIMARY KEY (id);


--
-- Name: fisher_angler_profiles fisher_angler_profiles_player_id_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_angler_profiles
    ADD CONSTRAINT fisher_angler_profiles_player_id_key UNIQUE (player_id);


--
-- Name: fisher_asset_showcase fisher_asset_showcase_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_asset_showcase
    ADD CONSTRAINT fisher_asset_showcase_pkey PRIMARY KEY (id);


--
-- Name: fisher_assets fisher_assets_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_assets
    ADD CONSTRAINT fisher_assets_pkey PRIMARY KEY (id);


--
-- Name: fisher_audit_log fisher_audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_audit_log
    ADD CONSTRAINT fisher_audit_log_pkey PRIMARY KEY (id);


--
-- Name: fisher_bottles fisher_bottles_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_bottles
    ADD CONSTRAINT fisher_bottles_pkey PRIMARY KEY (id);


--
-- Name: fisher_catch_gallery fisher_catch_gallery_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_catch_gallery
    ADD CONSTRAINT fisher_catch_gallery_pkey PRIMARY KEY (id);


--
-- Name: fisher_club_members fisher_club_members_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_club_members
    ADD CONSTRAINT fisher_club_members_pkey PRIMARY KEY (id);


--
-- Name: fisher_clubs fisher_clubs_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_clubs
    ADD CONSTRAINT fisher_clubs_pkey PRIMARY KEY (id);


--
-- Name: fisher_diaries fisher_diaries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_diaries
    ADD CONSTRAINT fisher_diaries_pkey PRIMARY KEY (id);


--
-- Name: fisher_fisheries fisher_fisheries_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_fisheries
    ADD CONSTRAINT fisher_fisheries_pkey PRIMARY KEY (id);


--
-- Name: fisher_orders fisher_orders_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_orders
    ADD CONSTRAINT fisher_orders_pkey PRIMARY KEY (id);


--
-- Name: fisher_players fisher_players_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_players
    ADD CONSTRAINT fisher_players_pkey PRIMARY KEY (id);


--
-- Name: fisher_real_catches fisher_real_catches_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_real_catches
    ADD CONSTRAINT fisher_real_catches_pkey PRIMARY KEY (id);


--
-- Name: fisher_species fisher_species_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_species
    ADD CONSTRAINT fisher_species_pkey PRIMARY KEY (id);


--
-- Name: fisher_spots fisher_spots_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_spots
    ADD CONSTRAINT fisher_spots_pkey PRIMARY KEY (id);


--
-- Name: fisher_workers fisher_workers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_workers
    ADD CONSTRAINT fisher_workers_pkey PRIMARY KEY (id);


--
-- Name: ix_fisher_players_dev_key; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX ix_fisher_players_dev_key ON public.fisher_players USING btree (dev_key);


--
-- Name: ix_fisher_players_openid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fisher_players_openid ON public.fisher_players USING btree (openid);


--
-- Name: ix_fisher_species_spot_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX ix_fisher_species_spot_id ON public.fisher_species USING btree (spot_id);


--
-- Name: fisher_angler_profiles fisher_angler_profiles_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_angler_profiles
    ADD CONSTRAINT fisher_angler_profiles_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.fisher_players(id);


--
-- Name: fisher_asset_showcase fisher_asset_showcase_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_asset_showcase
    ADD CONSTRAINT fisher_asset_showcase_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.fisher_players(id);


--
-- Name: fisher_assets fisher_assets_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_assets
    ADD CONSTRAINT fisher_assets_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.fisher_players(id);


--
-- Name: fisher_bottles fisher_bottles_picker_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_bottles
    ADD CONSTRAINT fisher_bottles_picker_id_fkey FOREIGN KEY (picker_id) REFERENCES public.fisher_players(id);


--
-- Name: fisher_bottles fisher_bottles_thrower_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_bottles
    ADD CONSTRAINT fisher_bottles_thrower_id_fkey FOREIGN KEY (thrower_id) REFERENCES public.fisher_players(id);


--
-- Name: fisher_catch_gallery fisher_catch_gallery_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_catch_gallery
    ADD CONSTRAINT fisher_catch_gallery_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.fisher_players(id);


--
-- Name: fisher_club_members fisher_club_members_club_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_club_members
    ADD CONSTRAINT fisher_club_members_club_id_fkey FOREIGN KEY (club_id) REFERENCES public.fisher_clubs(id);


--
-- Name: fisher_club_members fisher_club_members_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_club_members
    ADD CONSTRAINT fisher_club_members_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.fisher_players(id);


--
-- Name: fisher_clubs fisher_clubs_creator_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_clubs
    ADD CONSTRAINT fisher_clubs_creator_id_fkey FOREIGN KEY (creator_id) REFERENCES public.fisher_players(id);


--
-- Name: fisher_diaries fisher_diaries_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_diaries
    ADD CONSTRAINT fisher_diaries_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.fisher_players(id);


--
-- Name: fisher_fisheries fisher_fisheries_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_fisheries
    ADD CONSTRAINT fisher_fisheries_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.fisher_players(id);


--
-- Name: fisher_orders fisher_orders_buyer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_orders
    ADD CONSTRAINT fisher_orders_buyer_id_fkey FOREIGN KEY (buyer_id) REFERENCES public.fisher_players(id);


--
-- Name: fisher_orders fisher_orders_seller_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_orders
    ADD CONSTRAINT fisher_orders_seller_id_fkey FOREIGN KEY (seller_id) REFERENCES public.fisher_players(id);


--
-- Name: fisher_real_catches fisher_real_catches_player_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_real_catches
    ADD CONSTRAINT fisher_real_catches_player_id_fkey FOREIGN KEY (player_id) REFERENCES public.fisher_players(id);


--
-- Name: fisher_species fisher_species_spot_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_species
    ADD CONSTRAINT fisher_species_spot_id_fkey FOREIGN KEY (spot_id) REFERENCES public.fisher_spots(id);


--
-- Name: fisher_workers fisher_workers_fishery_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.fisher_workers
    ADD CONSTRAINT fisher_workers_fishery_id_fkey FOREIGN KEY (fishery_id) REFERENCES public.fisher_fisheries(id);


--
-- PostgreSQL database dump complete
--

\unrestrict TG4XQKZWxFJ4CpJ686AcThKFggD8xhYAFcBBrCsHEF1CdbcJeMmPsEgkLBVYnEP

